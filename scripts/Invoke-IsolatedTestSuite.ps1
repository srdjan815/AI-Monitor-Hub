[CmdletBinding()]
param(
    [ValidateSet("full", "supplier", "random", "stress")]
    [string]$Suite = "full",

    [ValidateRange(1, 20)]
    [int]$RandomRuns = 5,

    [ValidateRange(0, 2147483646)]
    [int]$RandomSeed = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot "docker-compose.test-isolated.yml"
$runId = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$projectName = "amh-test-$runId"
$expectedDatabase = "amh_ephemeral_test_only"
$cleanupRequired = $true
$exitCode = 0

function Invoke-TestCompose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & docker compose --project-name $projectName --file $composeFile @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose command failed with exit code $LASTEXITCODE."
    }
}

function Assert-TestOnlyConfiguration {
    if (-not (Test-Path -LiteralPath $composeFile)) {
        throw "Missing isolated test Compose file: $composeFile"
    }
    if ($projectName -notmatch '^amh-test-[a-f0-9]{12}$') {
        throw "Unsafe Compose project name: $projectName"
    }
    $configuration = (& docker compose --project-name $projectName --file $composeFile config) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "Isolated test Compose configuration is invalid."
    }
    $requiredMarkers = @(
        "APP_ENV: test",
        "SUPPLIER_SECRET_MODE: test_memory",
        $expectedDatabase,
        "TEST_ONLY_EPHEMERAL"
    )
    foreach ($marker in $requiredMarkers) {
        if (-not $configuration.Contains($marker)) {
            throw "Safety marker is missing from test configuration: $marker"
        }
    }
    if ($configuration -match '(?m)^\s+ports:' -or
        $configuration.Contains("supplier-secrets.json") -or
        $configuration.Contains("postgres_data") -or
        $configuration.Contains("redis_data") -or
        $configuration.Contains("ai_cenovnici")) {
        throw "Unsafe development/production resource detected in isolated test configuration."
    }
}

function Invoke-PytestRun {
    param([string[]]$PytestArguments)
    Write-Host "`n[TEST ONLY] pytest $($PytestArguments -join ' ')" -ForegroundColor Yellow
    & docker compose --project-name $projectName --file $composeFile run --rm test-runner python -m pytest @PytestArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Test run failed with exit code $LASTEXITCODE."
    }
}

function Remove-TestEnvironment {
    param([switch]$RemoveImages)
    Write-Host "[TEST ONLY] Removing disposable database, Redis, containers, network and volumes..." -ForegroundColor Yellow
    $downArguments = @("down", "--volumes", "--remove-orphans", "--timeout", "10")
    if ($RemoveImages) {
        $downArguments += @("--rmi", "local")
    }
    & docker compose --project-name $projectName --file $composeFile @downArguments
    $downExitCode = $LASTEXITCODE
    $leftovers = @(& docker ps --all --quiet --filter "label=com.docker.compose.project=$projectName")
    $networks = @(& docker network ls --quiet --filter "label=com.docker.compose.project=$projectName")
    $volumes = @(& docker volume ls --quiet --filter "label=com.docker.compose.project=$projectName")
    $images = @()
    if ($RemoveImages) {
        $images = @(& docker image ls --quiet --filter "reference=$projectName-*")
    }
    if ($downExitCode -ne 0 -or $leftovers.Count -gt 0 -or $networks.Count -gt 0 -or $volumes.Count -gt 0 -or $images.Count -gt 0) {
        throw "Cleanup verification failed for isolated project $projectName. Manual review is required."
    }
    Write-Host "[TEST ONLY] Cleanup verified: no resources remain for $projectName." -ForegroundColor Green
}

function Invoke-OneIsolatedRun {
    param([string[]]$PytestArguments)
    try {
        Invoke-TestCompose up --detach --wait test-api
        Invoke-PytestRun $PytestArguments
    }
    finally {
        Remove-TestEnvironment
    }
}

Write-Host "============================================================" -ForegroundColor Red
Write-Host " TEST ONLY / EPHEMERAL / NO REAL DATA / NOT FOR DEVELOPMENT " -ForegroundColor Red
Write-Host " Project: $projectName" -ForegroundColor Yellow
Write-Host " Database: $expectedDatabase (created and destroyed this run)" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Red

try {
    Assert-TestOnlyConfiguration
    Invoke-TestCompose build test-api test-runner

    switch ($Suite) {
        "supplier" {
            Invoke-OneIsolatedRun @("-q", "-k", "supplier")
        }
        "random" {
            for ($index = 1; $index -le $RandomRuns; $index++) {
                $seed = if ($RandomSeed -gt 0) {
                    $RandomSeed + $index - 1
                } else {
                    Get-Random -Minimum 1 -Maximum 2147483646
                }
                Invoke-OneIsolatedRun @("-q", "--randomly-seed=$seed")
            }
        }
        "stress" {
            Invoke-OneIsolatedRun @("-q")
            for ($index = 1; $index -le $RandomRuns; $index++) {
                $seed = if ($RandomSeed -gt 0) {
                    $RandomSeed + $index - 1
                } else {
                    Get-Random -Minimum 1 -Maximum 2147483646
                }
                Invoke-OneIsolatedRun @("-q", "--randomly-seed=$seed")
            }
            Invoke-OneIsolatedRun @(
                "-q",
                "-n", "auto",
                # Only read-only architecture/static tests belong here. Tests
                # that use PostgreSQL or Redis already exercise concurrency
                # internally and must not share one database across xdist workers.
                "tests/test_attribute_platform_decomposition.py",
                "tests/test_catalog_decomposition.py",
                "tests/test_inventory_decomposition.py",
                "tests/test_module_boundaries.py",
                "tests/test_product_attribute_decomposition.py",
                "tests/test_product_content_decomposition.py",
                "tests/test_supplier_acquisition_architecture.py",
                "tests/test_supplier_architecture.py",
                "tests/test_supplier_delta_architecture.py",
                "tests/test_supplier_incident_architecture.py",
                "tests/test_supplier_mapping_architecture.py",
                "tests/test_supplier_schema_architecture.py",
                "tests/test_supplier_snapshot_architecture.py",
                "tests/test_static_baseline.py"
            )
        }
        default {
            Invoke-OneIsolatedRun @("-q")
        }
    }
}
catch {
    $exitCode = 1
    Write-Host "[TEST ONLY] FAILURE: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if ($cleanupRequired) {
        try {
            Remove-TestEnvironment -RemoveImages
        }
        catch {
            $exitCode = 2
            Write-Host "[TEST ONLY] CLEANUP FAILURE: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

exit $exitCode
