[CmdletBinding()]
param(
    [ValidateSet('Menu','Start','Stop','Restart','Status','Health','Logs','Open')]
    [string]$Action = 'Menu'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot       = 'C:\AI-Monitor-Hub'
$FrontendRoot      = Join-Path $ProjectRoot 'frontend'
$ApiBaseUrl        = 'http://localhost:8000'
$ApiDocsUrl        = "$ApiBaseUrl/docs"
$OpenApiUrl        = "$ApiBaseUrl/api/v1/openapi.json"
$FrontendPreferred = 5173
$FrontendFallback  = 5174
$FrontendPidFile   = Join-Path $ProjectRoot '.frontend-vite.pid'
$FrontendLogFile   = Join-Path $ProjectRoot 'frontend-vite.log'
$SecretsEnvFile    = Join-Path $ProjectRoot '.env.secrets'
$SupplierSecrets   = Join-Path $ProjectRoot 'config\supplier-secrets.json'
$NpmCommand        = $null

function Write-Title {
    Clear-Host
    Write-Host '=============================================' -ForegroundColor Cyan
    Write-Host '           AI MONITOR HUB LAUNCHER           ' -ForegroundColor Cyan
    Write-Host '=============================================' -ForegroundColor Cyan
    Write-Host ''
}

function Assert-ProjectStructure {
    if (-not (Test-Path $ProjectRoot)) { throw "Projekat nije pronadjen: $ProjectRoot" }

    $composeExists = (Test-Path (Join-Path $ProjectRoot 'docker-compose.yml')) -or
                     (Test-Path (Join-Path $ProjectRoot 'compose.yml')) -or
                     (Test-Path (Join-Path $ProjectRoot 'compose.yaml'))
    if (-not $composeExists) { throw "Docker Compose fajl nije pronadjen u: $ProjectRoot" }
    if (-not (Test-Path (Join-Path $FrontendRoot 'package.json'))) {
        throw "Frontend package.json nije pronadjen u: $FrontendRoot"
    }
}

function Get-AdminToken {
    if (-not (Test-Path -LiteralPath $SecretsEnvFile -PathType Leaf)) {
        throw "Nedostaje konfiguracioni fajl: $SecretsEnvFile"
    }
    $line = Get-Content -LiteralPath $SecretsEnvFile |
        Where-Object { $_ -match '^\s*AI_MONITOR_ADMIN_TOKEN\s*=' } |
        Select-Object -Last 1
    if (-not $line) {
        throw 'AI_MONITOR_ADMIN_TOKEN nije podesen u .env.secrets.'
    }
    $token = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
    if ($token.Length -lt 32) {
        throw 'AI_MONITOR_ADMIN_TOKEN mora imati najmanje 32 znaka.'
    }
    return $token
}

function Assert-SecretConfiguration {
    $null = Get-AdminToken
    if (-not (Test-Path -LiteralPath $SupplierSecrets -PathType Leaf)) {
        throw "Nedostaje konfiguracioni fajl: $SupplierSecrets"
    }
    try {
        $parsed = Get-Content -Raw -LiteralPath $SupplierSecrets | ConvertFrom-Json
    } catch {
        throw 'supplier-secrets.json nije validan JSON.'
    }
    if ($null -eq $parsed -or $parsed -isnot [PSCustomObject]) {
        throw 'supplier-secrets.json mora sadrzati JSON objekat.'
    }
}

function Test-CommandAvailable([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Start-DockerDesktopIfNeeded {
    & docker info *> $null
    if ($LASTEXITCODE -eq 0) { return }

    $dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $dockerDesktop -PathType Leaf)) {
        throw 'Docker Engine nije dostupan, a Docker Desktop nije pronadjen.'
    }
    Write-Host 'Pokrecem Docker Desktop...' -ForegroundColor Yellow
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 3
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) { return }
    } while ((Get-Date) -lt $deadline)
    throw 'Docker Desktop nije postao dostupan u ocekivanom roku.'
}

function Assert-Prerequisites {
    Assert-ProjectStructure
    Assert-SecretConfiguration
    if (-not (Test-CommandAvailable 'docker')) { throw 'Docker nije pronadjen. Pokrenite Docker Desktop.' }
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($npm) {
        $script:NpmCommand = $npm.Source
    } else {
        $standardNpm = Join-Path $env:ProgramFiles 'nodejs\npm.cmd'
        if (-not (Test-Path -LiteralPath $standardNpm -PathType Leaf)) {
            throw 'npm nije pronadjen. Instalirajte Node.js LTS.'
        }
        $env:PATH = "$(Split-Path -Parent $standardNpm);$env:PATH"
        $script:NpmCommand = $standardNpm
    }

    Start-DockerDesktopIfNeeded
}

function Wait-TcpPort {
    param([Parameter(Mandatory)][int]$Port, [int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $client = $null
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
            if ($async.AsyncWaitHandle.WaitOne(1000, $false) -and $client.Connected) {
                $client.EndConnect($async)
                $client.Close()
                return $true
            }
        } catch { }
        finally { if ($client) { $client.Close() } }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Test-HttpOk {
    param([Parameter(Mandatory)][string]$Url, [int]$TimeoutSeconds = 8)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
    } catch { return $false }
}

function Get-FreeFrontendPort {
    foreach ($port in @($FrontendPreferred, $FrontendFallback)) {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) { return $port }
    }
    throw "Portovi $FrontendPreferred i $FrontendFallback su zauzeti."
}

function Get-FrontendProcess {
    if (Test-Path $FrontendPidFile) {
        $rawPid = Get-Content $FrontendPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($rawPid -match '^\d+$') {
            $proc = Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue
            if ($proc) { return $proc }
        }
    }
    return $null
}

function Get-RunningFrontendPort {
    foreach ($port in @($FrontendPreferred, $FrontendFallback)) {
        if (Test-HttpOk -Url "http://localhost:$port") { return $port }
    }
    return $null
}

function Start-DockerServices {
    Write-Host 'Pokrecem Docker servise...' -ForegroundColor Yellow
    Push-Location $ProjectRoot
    try {
        & docker compose up -d
        if ($LASTEXITCODE -ne 0) { throw 'docker compose up nije uspeo.' }
    } finally { Pop-Location }

    Write-Host 'Cekam API i zavisne servise...' -ForegroundColor DarkGray
    if (-not (Wait-TcpPort -Port 8000 -TimeoutSeconds 90)) {
        throw 'API port 8000 nije postao dostupan u ocekivanom roku.'
    }
    $deadline = (Get-Date).AddSeconds(120)
    do {
        $ready = $true
        Push-Location $ProjectRoot
        try {
            foreach ($service in @('api','db','redis','worker')) {
                $containerId = (& docker compose ps -q $service 2>$null | Select-Object -First 1)
                if (-not $containerId) { $ready = $false; continue }
                $state = & docker inspect -f '{{.State.Status}}' $containerId 2>$null
                if ($state -ne 'running') { $ready = $false }
                $health = & docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $containerId 2>$null
                if ($health -notin @('healthy','none')) { $ready = $false }
            }
        } finally { Pop-Location }
        if (-not $ready) { Start-Sleep -Seconds 2 }
    } while (-not $ready -and (Get-Date) -lt $deadline)
    if (-not $ready) { throw 'Docker servisi nisu postali spremni u ocekivanom roku.' }

    $token = Get-AdminToken
    try {
        $headers = @{ Authorization = "Bearer $token" }
        $null = Invoke-WebRequest -Uri "$ApiBaseUrl/api/v1/suppliers?limit=1" `
            -Headers $headers -UseBasicParsing -TimeoutSec 10
    } catch {
        throw 'API ne prihvata podeseni AI_MONITOR_ADMIN_TOKEN.'
    } finally {
        $token = $null
        $headers = $null
    }
}

function Start-Frontend {
    $existingPort = Get-RunningFrontendPort
    if ($existingPort) {
        Write-Host "Frontend vec radi na portu $existingPort." -ForegroundColor Green
        return $existingPort
    }

    $tracked = Get-FrontendProcess
    if ($tracked) {
        Stop-Process -Id $tracked.Id -Force -ErrorAction SilentlyContinue
        Remove-Item $FrontendPidFile -Force -ErrorAction SilentlyContinue
    }

    $port = Get-FreeFrontendPort
    Write-Host "Pokrecem frontend na portu $port..." -ForegroundColor Yellow

    $command = "Set-Location '$FrontendRoot'; & '$NpmCommand' run dev -- --host 0.0.0.0 --port $port *> '$FrontendLogFile'"
    $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-Command',$command)
    $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Minimized -PassThru
    Set-Content -Path $FrontendPidFile -Value $proc.Id -Encoding Ascii

    if (-not (Wait-TcpPort -Port $port -TimeoutSeconds 60)) {
        throw "Frontend nije dostupan na portu $port. Pogledajte: $FrontendLogFile"
    }
    return $port
}

function Start-Platform {
    Assert-Prerequisites
    Start-DockerServices
    $frontendPort = Start-Frontend
    Write-Host ''
    Write-Host 'Platforma je pokrenuta.' -ForegroundColor Green
    Write-Host "Frontend:  http://localhost:$frontendPort" -ForegroundColor Green
    Write-Host "Dashboard: http://localhost:$frontendPort/dashboard" -ForegroundColor Green
    Write-Host "Swagger:   $ApiDocsUrl" -ForegroundColor Green
    Start-Process "http://localhost:$frontendPort/dashboard"
}

function Stop-Frontend {
    $proc = Get-FrontendProcess
    if ($proc) {
        Write-Host "Gasim frontend PID $($proc.Id)..." -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host 'Evidentirani frontend proces nije pronadjen.' -ForegroundColor DarkGray
    }
    Remove-Item $FrontendPidFile -Force -ErrorAction SilentlyContinue
}

function Stop-Platform {
    Assert-ProjectStructure
    Stop-Frontend
    Write-Host 'Zaustavljam Docker servise...' -ForegroundColor Yellow
    Push-Location $ProjectRoot
    try {
        & docker compose down
        if ($LASTEXITCODE -ne 0) { throw 'docker compose down nije uspeo.' }
    } finally { Pop-Location }
    Write-Host 'Platforma je zaustavljena. Podaci i volumeni nisu obrisani.' -ForegroundColor Green
}

function Show-Status {
    Assert-ProjectStructure
    Write-Host 'Docker Compose status:' -ForegroundColor Cyan
    Push-Location $ProjectRoot
    try { & docker compose ps } finally { Pop-Location }
    $port = Get-RunningFrontendPort
    Write-Host ''
    if ($port) { Write-Host "Frontend: RADI na http://localhost:$port" -ForegroundColor Green }
    else { Write-Host 'Frontend: NE RADI' -ForegroundColor Red }
}

function Show-Health {
    Assert-Prerequisites
    $checks = [ordered]@{}
    $checks['Docker Engine'] = $true
    $checks['API port 8000'] = Wait-TcpPort -Port 8000 -TimeoutSeconds 2
    $checks['Swagger'] = Test-HttpOk -Url $ApiDocsUrl
    $checks['OpenAPI'] = Test-HttpOk -Url $OpenApiUrl
    $checks['Frontend'] = [bool](Get-RunningFrontendPort)

    Push-Location $ProjectRoot
    try {
        foreach ($service in @('api','db','redis','worker')) {
            $containerId = (& docker compose ps -q $service 2>$null | Select-Object -First 1)
            $running = $false
            if ($containerId) {
                $state = & docker inspect -f '{{.State.Status}}' $containerId 2>$null
                $running = ($state -eq 'running')
            }
            $checks["Docker: $service"] = $running
        }
    } finally { Pop-Location }

    Write-Host ''
    Write-Host 'HEALTH CHECK' -ForegroundColor Cyan
    Write-Host '------------'
    foreach ($item in $checks.GetEnumerator()) {
        if ($item.Value) { Write-Host ('{0,-25} OK' -f $item.Key) -ForegroundColor Green }
        else { Write-Host ('{0,-25} GRESKA' -f $item.Key) -ForegroundColor Red }
    }
    Write-Host ''
    if (-not ($checks.Values -contains $false)) {
        Write-Host 'UKUPNO: PLATFORMA JE SPREMNA' -ForegroundColor Green
    } else {
        Write-Host 'UKUPNO: POTREBNA JE PROVERA' -ForegroundColor Yellow
    }
}

function Show-LogsMenu {
    Write-Host '1. API logovi'
    Write-Host '2. Worker logovi'
    Write-Host '3. Svi Docker logovi'
    Write-Host '4. Frontend log'
    $logChoice = Read-Host 'Izbor'
    Push-Location $ProjectRoot
    try {
        switch ($logChoice) {
            '1' { & docker compose logs api --tail 150 }
            '2' { & docker compose logs worker --tail 150 }
            '3' { & docker compose logs --tail 150 }
            '4' {
                if (Test-Path $FrontendLogFile) { Get-Content $FrontendLogFile -Tail 150 }
                else { Write-Host 'Frontend log jos ne postoji.' -ForegroundColor Yellow }
            }
            default { Write-Host 'Nepoznat izbor.' -ForegroundColor Yellow }
        }
    } finally { Pop-Location }
}

function Open-Platform {
    $port = Get-RunningFrontendPort
    if (-not $port) { throw 'Frontend trenutno nije dostupan.' }
    Start-Process "http://localhost:$port/dashboard"
}

function Invoke-Action([string]$SelectedAction) {
    switch ($SelectedAction) {
        'Start'   { Start-Platform }
        'Stop'    { Stop-Platform }
        'Restart' { Stop-Platform; Start-Sleep -Seconds 2; Start-Platform }
        'Status'  { Show-Status }
        'Health'  { Show-Health }
        'Logs'    { Show-LogsMenu }
        'Open'    { Open-Platform }
        default   { throw "Nepoznata akcija: $SelectedAction" }
    }
}

if ($Action -ne 'Menu') {
    try { Invoke-Action $Action }
    catch {
        Write-Host ''
        Write-Host "GRESKA: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    exit 0
}

while ($true) {
    Write-Title
    Write-Host '1. Pokreni platformu'
    Write-Host '2. Zaustavi platformu'
    Write-Host '3. Restartuj platformu'
    Write-Host '4. Status servisa'
    Write-Host '5. Health check'
    Write-Host '6. Otvori Dashboard'
    Write-Host '7. Prikazi logove'
    Write-Host '8. Otvori Swagger'
    Write-Host '0. Izlaz'
    Write-Host ''

    $choice = Read-Host 'Izaberite opciju'
    try {
        switch ($choice) {
            '1' { Start-Platform }
            '2' { Stop-Platform }
            '3' { Stop-Platform; Start-Sleep -Seconds 2; Start-Platform }
            '4' { Show-Status }
            '5' { Show-Health }
            '6' { Open-Platform }
            '7' { Show-LogsMenu }
            '8' { Start-Process $ApiDocsUrl }
            '0' { break }
            default { Write-Host 'Nepostojeca opcija.' -ForegroundColor Yellow }
        }
    } catch {
        Write-Host ''
        Write-Host "GRESKA: $($_.Exception.Message)" -ForegroundColor Red
    }

    if ($choice -ne '0') {
        Write-Host ''
        Read-Host 'Pritisnite Enter za povratak u meni' | Out-Null
    }
}
