$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Backup Imagen USB.lnk'
$pythonwPath = $null
if (Test-Path -LiteralPath $shortcutPath) {
    $shell = New-Object -ComObject WScript.Shell
    $pythonwPath = $shell.CreateShortcut($shortcutPath).TargetPath
    Remove-Item -LiteralPath $shortcutPath
    Write-Host 'Se quitó Backup Imagen del inicio de sesión.'
} else {
    Write-Host 'No se encontró el acceso directo de Backup Imagen.'
}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match '(?i)-m\s+backup_imagen\s+--watch' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$pythonPath = $null
if ($pythonwPath) {
    $siblingPython = Join-Path (Split-Path -Parent $pythonwPath) 'python.exe'
    if (Test-Path -LiteralPath $siblingPython) {
        $pythonPath = $siblingPython
    }
}
if ($pythonPath) {
    & $pythonPath -m pip uninstall -y backup-imagen
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo desinstalar Backup Imagen del entorno Python asociado al monitor.'
    }
}
