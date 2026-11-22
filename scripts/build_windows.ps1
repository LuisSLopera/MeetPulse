$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $ProjectRoot

$PythonExecutable = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "No se encontro el entorno virtual: $PythonExecutable. Cree .venv e instale .[build]."
}

# Windows PowerShell 5.1 convierte cualquier salida stderr de un programa nativo
# en NativeCommandError cuando ErrorActionPreference es Stop. PyInstaller envia
# sus mensajes INFO por stderr aunque termine correctamente, por lo que durante
# esta llamada se valida $LASTEXITCODE en lugar del canal usado para los mensajes.
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $PythonExecutable -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name ZoomMonitor `
    --specpath (Join-Path $ProjectRoot 'build') `
    --workpath (Join-Path $ProjectRoot 'build\work') `
    --distpath (Join-Path $ProjectRoot 'dist') `
    --icon (Join-Path $ProjectRoot 'assets\logo.png') `
    --paths (Join-Path $ProjectRoot 'src') `
    (Join-Path $ProjectRoot 'scripts\build_entry.py')
$PyInstallerExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference

if ($PyInstallerExitCode -ne 0) {
    throw "PyInstaller termino con codigo de salida $PyInstallerExitCode."
}

$PackageDirectory = Join-Path $ProjectRoot 'dist\ZoomMonitor-Windows'
New-Item -ItemType Directory -Path $PackageDirectory -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'dist\ZoomMonitor.exe') -Destination $PackageDirectory -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot '.env.example') -Destination (Join-Path $PackageDirectory '.env.example') -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'docs\INSTRUCCIONES_WINDOWS.txt') -Destination $PackageDirectory -Force

$ZipPath = Join-Path $ProjectRoot 'dist\ZoomMonitor-Windows.zip'
Compress-Archive -Path (Join-Path $PackageDirectory '*') -DestinationPath $ZipPath -Force

Write-Host "Paquete creado en: $PackageDirectory"
Write-Host "ZIP para distribuir: $ZipPath"
