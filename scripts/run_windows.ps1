$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$VenvPath = Join-Path $ProjectRoot ".venv-windows"
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.12 -m venv $VenvPath
    }
    else {
        python -m venv $VenvPath
    }
}

& $PythonPath -m pip install -r requirements.txt
& $PythonPath main.py