$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$items = @(
    @{ Name='AI Monitor Hub - Pokreni.lnk'; Target=(Join-Path $scriptDir 'Start-AI-Monitor-Hub.cmd') },
    @{ Name='AI Monitor Hub - Meni.lnk'; Target=(Join-Path $scriptDir 'AI-Monitor-Hub-Menu.cmd') },
    @{ Name='AI Monitor Hub - Zaustavi.lnk'; Target=(Join-Path $scriptDir 'Stop-AI-Monitor-Hub.cmd') }
)
foreach ($item in $items) {
    $shortcut = $shell.CreateShortcut((Join-Path $desktop $item.Name))
    $shortcut.TargetPath = $item.Target
    $shortcut.WorkingDirectory = $scriptDir
    $shortcut.Save()
}
Write-Host 'Precice su napravljene na Desktopu.' -ForegroundColor Green
Read-Host 'Pritisnite Enter za izlaz' | Out-Null
