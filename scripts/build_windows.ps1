$ErrorActionPreference = "Stop"

# ============================================================
# Projektverzeichnis finden
# ============================================================

$CurrentDirectory = $PSScriptRoot
$ProjectRoot = $null

while ($CurrentDirectory) {

    $MainFile = Join-Path $CurrentDirectory "main.py"
    $AppDirectory = Join-Path $CurrentDirectory "app"

    if (
        (Test-Path $MainFile) -and
        (Test-Path $AppDirectory)
    ) {
        $ProjectRoot = $CurrentDirectory
        break
    }

    $ParentDirectory = Split-Path -Parent $CurrentDirectory

    if (
        -not $ParentDirectory -or
        $ParentDirectory -eq $CurrentDirectory
    ) {
        break
    }

    $CurrentDirectory = $ParentDirectory
}

if (-not $ProjectRoot) {
    throw "Projektordner konnte nicht gefunden werden. main.py und app\ fehlen."
}

Set-Location $ProjectRoot

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Genshin Mod Manager - Windows Build" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Projekt: $ProjectRoot"
Write-Host ""

# ============================================================
# Windows Virtual Environment
# ============================================================

$VenvPath = Join-Path $ProjectRoot ".venv-windows"

$PythonPath = Join-Path `
    $VenvPath `
    "Scripts\python.exe"

Write-Host "Venv:   $VenvPath"
Write-Host "Python: $PythonPath"
Write-Host ""

# ============================================================
# Venv erstellen
# ============================================================

if (-not (Test-Path $PythonPath)) {

    Write-Host "Windows-Venv wurde nicht gefunden." -ForegroundColor Yellow
    Write-Host "Erstelle .venv-windows ..."
    Write-Host ""

    if (Get-Command py -ErrorAction SilentlyContinue) {

        Write-Host "Verwende Python Launcher: py"

        try {
            & py -3.12 -m venv $VenvPath
        }
        catch {
            Write-Host "Python 3.12 konnte nicht verwendet werden." -ForegroundColor Yellow
            Write-Host "Versuche Standard-Python ..."

            & py -3 -m venv $VenvPath
        }
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {

        Write-Host "Verwende python.exe"

        & python -m venv $VenvPath
    }
    else {

        throw @"
Python wurde nicht gefunden.

Installiere Python 3.12 oder neuer und stelle sicher,
dass entweder 'py' oder 'python' in PATH verfügbar ist.
"@
    }
}

# ============================================================
# Venv prüfen
# ============================================================

if (-not (Test-Path $PythonPath)) {

    throw "Python wurde in der virtuellen Umgebung nicht gefunden: $PythonPath"
}

Write-Host "Windows-Venv gefunden." -ForegroundColor Green
Write-Host ""

# ============================================================
# Python-Version
# ============================================================

Write-Host "Python-Version:"
& $PythonPath --version

Write-Host ""

# ============================================================
# pip aktualisieren
# ============================================================

Write-Host "[1/7] Aktualisiere pip ..." -ForegroundColor Cyan

& $PythonPath `
    -m pip `
    install `
    --upgrade `
    pip

if ($LASTEXITCODE -ne 0) {
    throw "pip konnte nicht aktualisiert werden."
}

# ============================================================
# Requirements
# ============================================================

Write-Host ""
Write-Host "[2/7] Installiere Abhängigkeiten ..." -ForegroundColor Cyan

$RequirementsFile = Join-Path `
    $ProjectRoot `
    "requirements.txt"

if (Test-Path $RequirementsFile) {

    & $PythonPath `
        -m pip `
        install `
        -r `
        $RequirementsFile

    if ($LASTEXITCODE -ne 0) {
        throw "requirements.txt konnte nicht installiert werden."
    }
}
else {

    Write-Host "Keine requirements.txt gefunden." -ForegroundColor Yellow
}

# ============================================================
# Build-Abhängigkeiten
# ============================================================

Write-Host ""
Write-Host "[3/7] Installiere Build-Abhängigkeiten ..." -ForegroundColor Cyan

& $PythonPath `
    -m pip `
    install `
    --upgrade `
    pyinstaller `
    packaging

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller/packaging konnte nicht installiert werden."
}

# ============================================================
# Quellcode prüfen
# ============================================================

Write-Host ""
Write-Host "[4/7] Prüfe Python-Dateien ..." -ForegroundColor Cyan

& $PythonPath `
    -m compileall `
    -q `
    app

if ($LASTEXITCODE -ne 0) {
    throw "Python-Compile-Test fehlgeschlagen."
}

# ============================================================
# Übersetzungen prüfen
# ============================================================

Write-Host ""
Write-Host "[5/7] Prüfe Übersetzungen ..." -ForegroundColor Cyan

$GermanLocale = Join-Path `
    $ProjectRoot `
    "app\i18n\locales\de.json"

$EnglishLocale = Join-Path `
    $ProjectRoot `
    "app\i18n\locales\en.json"

if (-not (Test-Path $GermanLocale)) {
    throw "Deutsche Übersetzung fehlt: $GermanLocale"
}

if (-not (Test-Path $EnglishLocale)) {
    throw "Englische Übersetzung fehlt: $EnglishLocale"
}

& $PythonPath `
    -m json.tool `
    $GermanLocale `
    *> $null

if ($LASTEXITCODE -ne 0) {
    throw "de.json enthält ungültiges JSON."
}

& $PythonPath `
    -m json.tool `
    $EnglishLocale `
    *> $null

if ($LASTEXITCODE -ne 0) {
    throw "en.json enthält ungültiges JSON."
}

# ============================================================
# Alte Builds entfernen
# ============================================================

Write-Host ""
Write-Host "[6/7] Entferne alte Build-Ausgaben ..." -ForegroundColor Cyan

$BuildDirectory = Join-Path `
    $ProjectRoot `
    "build"

$DistDirectory = Join-Path `
    $ProjectRoot `
    "dist"

if (Test-Path $BuildDirectory) {

    Remove-Item `
        $BuildDirectory `
        -Recurse `
        -Force
}

if (Test-Path $DistDirectory) {

    Remove-Item `
        $DistDirectory `
        -Recurse `
        -Force
}

# ============================================================
# PyInstaller Argumente
# ============================================================

Write-Host ""
Write-Host "[7/7] Erstelle Windows-Anwendung ..." -ForegroundColor Cyan

$PyInstallerArguments = @(
    "--noconfirm"
    "--clean"
    "--windowed"

    "--name"
    "GenshinModManager"
)

# ------------------------------------------------------------
# Icon
# ------------------------------------------------------------

$IconPath = Join-Path `
    $ProjectRoot `
    "assets\icons\app.ico"

if (Test-Path $IconPath) {

    Write-Host "Icon: $IconPath"

    $PyInstallerArguments += @(
        "--icon"
        $IconPath
    )
}
else {

    Write-Host "Kein app.ico gefunden - Build ohne EXE-Icon." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# Assets
# ------------------------------------------------------------

$AssetsDirectory = Join-Path `
    $ProjectRoot `
    "assets"

if (Test-Path $AssetsDirectory) {

    $PyInstallerArguments += @(
        "--add-data"
        "$AssetsDirectory;assets"
    )
}

# ------------------------------------------------------------
# Übersetzungen
# ------------------------------------------------------------

$LocalesDirectory = Join-Path `
    $ProjectRoot `
    "app\i18n\locales"

if (Test-Path $LocalesDirectory) {

    $PyInstallerArguments += @(
        "--add-data"
        "$LocalesDirectory;app/i18n/locales"
    )
}

# ------------------------------------------------------------
# Stylesheets
# ------------------------------------------------------------

$StylesDirectory = Join-Path `
    $ProjectRoot `
    "app\styles"

if (Test-Path $StylesDirectory) {

    $PyInstallerArguments += @(
        "--add-data"
        "$StylesDirectory;app/styles"
    )
}

# ------------------------------------------------------------
# Einstiegspunkt
# ------------------------------------------------------------

$MainFile = Join-Path `
    $ProjectRoot `
    "main.py"

$PyInstallerArguments += $MainFile

# ============================================================
# Build
# ============================================================

& $PythonPath `
    -m PyInstaller `
    @PyInstallerArguments

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller-Build fehlgeschlagen."
}

# ============================================================
# Ergebnis prüfen
# ============================================================

$ApplicationDirectory = Join-Path `
    $DistDirectory `
    "GenshinModManager"

$ExecutablePath = Join-Path `
    $ApplicationDirectory `
    "GenshinModManager.exe"

if (-not (Test-Path $ExecutablePath)) {

    throw "Build wurde beendet, aber GenshinModManager.exe wurde nicht gefunden."
}

# ============================================================
# Fertig
# ============================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " BUILD ERFOLGREICH" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

Write-Host "Anwendung:"
Write-Host $ExecutablePath -ForegroundColor Green
Write-Host ""

Write-Host "Starten mit:"
Write-Host "`"$ExecutablePath`"" -ForegroundColor Cyan
Write-Host ""