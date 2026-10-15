$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonCommand = Get-Command python -ErrorAction Stop
$python = $pythonCommand.Source
$pythonPrefix = & $python -c "import sys; print(sys.prefix)"
$basePrefix = & $python -c "import sys; print(sys.base_prefix)"
$pythonDirectory = Split-Path -Parent $python
$pythonw = Join-Path $pythonDirectory 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) {
    $pythonwCommand = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pythonwCommand) {
        $pythonw = $pythonwCommand.Source
    }
}
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "No se encontró pythonw.exe junto a $python. Instala Python para Windows."
}

if ($pythonPrefix -eq $basePrefix) {
    $installArguments = @('--user', $repoRoot)
} else {
    $installArguments = @($repoRoot)
}
& $python -m pip install @installArguments
if ($LASTEXITCODE -ne 0) {
    throw 'No se pudo instalar Backup Imagen.'
}

$startupDirectory = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupDirectory 'Backup Imagen USB.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '-m backup_imagen --watch'
$shortcut.WorkingDirectory = $env:USERPROFILE
$shortcut.Description = 'Detecta el USB NTFS de 32 GB e inicia Backup Imagen.'
$shortcut.WindowStyle = 7
$shortcut.Save()

Start-Process -FilePath $pythonw -ArgumentList '-m backup_imagen --watch' -WorkingDirectory $repoRoot -WindowStyle Hidden

Write-Host 'Instalado y activado. El monitor también se iniciará en los siguientes inicios de sesión.'
Write-Host "Acceso directo: $shortcutPath"
