$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "Genshin Mod Manager - Windows Build"
Write-Host "Projekt: $ProjectRoot"
Write-Host ""

$VenvPath = Join-Path $ProjectRoot ".venv-windows"
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Host "Erstelle virtuelle Umgebung ..."

    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.12 -m venv $VenvPath
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv $VenvPath
    }
    else {
        throw "Python wurde nicht gefunden."
    }
}

Write-Host "Installiere Abhängigkeiten ..."

& $PythonPath -m pip install --upgrade pip
& $PythonPath -m pip install -r requirements.txt
& $PythonPath -m pip install pyinstaller

Write-Host "Entferne alte Build-Ausgaben ..."

if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}

if (Test-Path "dist") {
    Remove-Item "dist" -Recurse -Force
}

$PyInstallerArguments = @(
    "--noconfirm"
    "--clean"
    "--windowed"
    "--name"
    "GenshinModManager"
)

if (Test-Path "assets\icons\app.ico") {
    $PyInstallerArguments += @(
        "--icon"
        "assets\icons\app.ico"
    )
}

if (Test-Path "assets") {
    $PyInstallerArguments += @(
        "--add-data"
        "assets;assets"
    )
}

$PyInstallerArguments += "main.py"

Write-Host "Erstelle Anwendung ..."

& $PythonPath -m PyInstaller @PyInstallerArguments

Write-Host ""
Write-Host "Build abgeschlossen:"
Write-Host "$ProjectRoot\dist\GenshinModManager\"
Write-Host ""