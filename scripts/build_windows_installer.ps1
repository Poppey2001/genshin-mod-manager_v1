param(
    [Parameter(Mandatory = $false)]
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$Root = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

Set-Location $Root

Write-Host "Project root: $Root"
Write-Host "Build script: $PSCommandPath"

if (-not (
    Test-Path -LiteralPath (
        Join-Path $Root "main.py"
    )
)) {
    throw (
        "main.py was not found in the detected project root: " +
        $Root
    )
}

if (-not (
    Test-Path -LiteralPath (
        Join-Path $Root "app"
    )
)) {
    throw (
        "The app directory was not found in the detected project root: " +
        $Root
    )
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $VersionText = Get-Content `
        -LiteralPath (
            Join-Path $Root "app\version.py"
        ) `
        -Raw

    $Match = [regex]::Match(
        $VersionText,
        '(?m)^APP_VERSION\s*=\s*["'']([^"'']+)["'']'
    )

    if (-not $Match.Success) {
        throw "APP_VERSION was not found in app\version.py"
    }

    $Version = $Match.Groups[1].Value
}

$Version = $Version.TrimStart("v")

Write-Host "Building Windows installer version: $Version"

# ============================================================
# Python redistributable
# ============================================================

$PythonVersion = "3.12.10"
$PythonInstallerName = "python-$PythonVersion-amd64.exe"
$PythonInstallerUrl = (
    "https://www.python.org/ftp/python/" +
    "$PythonVersion/$PythonInstallerName"
)

# Official python.org index size for python-3.12.10-amd64.exe.
# The Authenticode signature is additionally verified below.
$ExpectedPythonInstallerSize = 26964224

$PythonRedistDirectory = Join-Path `
    $Root `
    "packaging\windows\redist"

$PythonInstaller = Join-Path `
    $PythonRedistDirectory `
    $PythonInstallerName

New-Item `
    -ItemType Directory `
    -Path $PythonRedistDirectory `
    -Force |
    Out-Null

$NeedPythonDownload = $true

if (Test-Path -LiteralPath $PythonInstaller) {
    $ExistingFile = Get-Item `
        -LiteralPath $PythonInstaller

    if (
        $ExistingFile.Length -eq
        $ExpectedPythonInstallerSize
    ) {
        $Signature = Get-AuthenticodeSignature `
            -LiteralPath $PythonInstaller

        if (
            $Signature.Status -eq "Valid" -and
            $Signature.SignerCertificate -and
            $Signature.SignerCertificate.Subject -match
            "Python Software Foundation"
        ) {
            $NeedPythonDownload = $false
            Write-Host (
                "Using cached official Python installer: " +
                $PythonInstaller
            )
        }
    }
}

if ($NeedPythonDownload) {
    if (Test-Path -LiteralPath $PythonInstaller) {
        Remove-Item `
            -LiteralPath $PythonInstaller `
            -Force
    }

    Write-Host (
        "Downloading official Python $PythonVersion installer..."
    )

    Invoke-WebRequest `
        -Uri $PythonInstallerUrl `
        -OutFile $PythonInstaller `
        -UseBasicParsing

    $DownloadedFile = Get-Item `
        -LiteralPath $PythonInstaller

    if (
        $DownloadedFile.Length -ne
        $ExpectedPythonInstallerSize
    ) {
        Remove-Item `
            -LiteralPath $PythonInstaller `
            -Force `
            -ErrorAction SilentlyContinue

        throw (
            "Downloaded Python installer has an unexpected size. " +
            "Expected $ExpectedPythonInstallerSize bytes, got " +
            "$($DownloadedFile.Length) bytes."
        )
    }

    $Signature = Get-AuthenticodeSignature `
        -LiteralPath $PythonInstaller

    if (
        $Signature.Status -ne "Valid" -or
        -not $Signature.SignerCertificate -or
        $Signature.SignerCertificate.Subject -notmatch
        "Python Software Foundation"
    ) {
        $Status = $Signature.Status
        $Subject = ""

        if ($Signature.SignerCertificate) {
            $Subject = (
                $Signature.SignerCertificate.Subject
            )
        }

        Remove-Item `
            -LiteralPath $PythonInstaller `
            -Force `
            -ErrorAction SilentlyContinue

        throw (
            "Python installer signature validation failed. " +
            "Status=$Status, Subject=$Subject"
        )
    }

    Write-Host "Python installer signature: VALID"
    Write-Host (
        "Signer: " +
        $Signature.SignerCertificate.Subject
    )
}

# ============================================================
# Build environment
# ============================================================

# ============================================================
# Python build dependencies
# ============================================================

python -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    throw (
        "pip upgrade failed with exit code " +
        "$LASTEXITCODE"
    )
}

$RequirementsFile = Join-Path `
    $Root `
    "requirements.txt"

if (Test-Path -LiteralPath $RequirementsFile) {
    Write-Host "Installing application requirements..."

    python -m pip install `
        -r $RequirementsFile

    if ($LASTEXITCODE -ne 0) {
        throw (
            "Application requirements installation failed " +
            "with exit code $LASTEXITCODE"
        )
    }
}
else {
    Write-Warning (
        "requirements.txt was not found. " +
        "Continuing with the currently installed Python packages."
    )
}

Write-Host "Installing PyInstaller build dependency..."

python -m pip install `
    "pyinstaller>=6.10,<7"

if ($LASTEXITCODE -ne 0) {
    throw (
        "PyInstaller installation failed with exit code " +
        "$LASTEXITCODE"
    )
}

foreach ($Directory in @(
    "build",
    "dist",
    "release"
)) {
    $Path = Join-Path $Root $Directory

    if (Test-Path -LiteralPath $Path) {
        Remove-Item `
            -LiteralPath $Path `
            -Recurse `
            -Force
    }
}

New-Item `
    -ItemType Directory `
    -Path (
        Join-Path $Root "release"
    ) `
    -Force |
    Out-Null

# ============================================================
# Frozen application
# ============================================================

python -m PyInstaller `
    --noconfirm `
    --clean `
    "packaging\GenshinModManager.spec"

if ($LASTEXITCODE -ne 0) {
    throw (
        "PyInstaller failed with exit code " +
        "$LASTEXITCODE"
    )
}

# ============================================================
# Inno Setup
# ============================================================

$ISCCCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)

$ISCC = (
    $ISCCCandidates |
    Where-Object {
        $_ -and (
            Test-Path -LiteralPath $_
        )
    } |
    Select-Object -First 1
)

if (-not $ISCC) {
    throw (
        "Inno Setup 6 was not found. " +
        "Install it first, for example with: " +
        "choco install innosetup -y"
    )
}

& $ISCC `
    "/DMyAppVersion=$Version" `
    "packaging\windows\installer.iss"

if ($LASTEXITCODE -ne 0) {
    throw (
        "Inno Setup failed with exit code " +
        "$LASTEXITCODE"
    )
}

$Installer = Join-Path `
    $Root `
    (
        "release\" +
        "Genshin-Mod-Manager-Setup-" +
        "$Version-x86_64.exe"
    )

if (-not (
    Test-Path -LiteralPath $Installer
)) {
    throw (
        "Installer was not created: " +
        $Installer
    )
}

$Hash = (
    Get-FileHash `
        -Algorithm SHA256 `
        -LiteralPath $Installer
).Hash.ToLowerInvariant()

$HashFile = "$Installer.sha256"

(
    "$Hash  " +
    (
        Split-Path `
            -Leaf `
            $Installer
    )
) |
Set-Content `
    -LiteralPath $HashFile `
    -Encoding ascii

Write-Host ""
Write-Host "Built:"
Write-Host "  $Installer"
Write-Host "  $HashFile"
Write-Host ""
Write-Host (
    "Bundled optional Python runtime: " +
    "$PythonVersion"
)
