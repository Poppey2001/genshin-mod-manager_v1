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

$SpecFile = Join-Path `
    $Root `
    "packaging\GenshinModManager.spec"

if (-not (
    Test-Path -LiteralPath $SpecFile
)) {
    throw (
        "PyInstaller spec file was not found: " +
        $SpecFile
    )
}

$SpecFile = (
    Resolve-Path `
        -LiteralPath $SpecFile
).Path

$MainPy = (
    Resolve-Path `
        -LiteralPath (
            Join-Path $Root "main.py"
        )
).Path

$AppDirectory = (
    Resolve-Path `
        -LiteralPath (
            Join-Path $Root "app"
        )
).Path

Write-Host ""
Write-Host "Resolved build paths:"
Write-Host "  Project root : $Root"
Write-Host "  main.py      : $MainPy"
Write-Host "  app          : $AppDirectory"
Write-Host "  spec         : $SpecFile"
Write-Host ""

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

Write-Host "Starting PyInstaller with ABSOLUTE spec path..."

python -m PyInstaller `
    --noconfirm `
    --clean `
    "$SpecFile"

if ($LASTEXITCODE -ne 0) {
    throw (
        "PyInstaller failed with exit code " +
        "$LASTEXITCODE"
    )
}

# ============================================================
# Inno Setup
# ============================================================

# ============================================================
# Inno Setup compiler
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
    Write-Host (
        "Inno Setup 6 is not installed. " +
        "Preparing a local portable build copy..."
    )

    $BuildToolsDirectory = Join-Path `
        $Root `
        ".build-tools"

    $InnoDirectory = Join-Path `
        $BuildToolsDirectory `
        "InnoSetup6"

    $InnoBootstrap = Join-Path `
        $BuildToolsDirectory `
        "innosetup-6-bootstrap.exe"

    New-Item `
        -ItemType Directory `
        -Path $BuildToolsDirectory `
        -Force |
        Out-Null

    $ISCC = Get-ChildItem `
        -LiteralPath $InnoDirectory `
        -Filter "ISCC.exe" `
        -File `
        -Recurse `
        -ErrorAction SilentlyContinue |
        Select-Object `
            -ExpandProperty FullName `
            -First 1

    if (-not $ISCC) {
        # The JRSoftware download wrapper can return an HTML
        # response to older PowerShell/IE web clients. Use the immutable
        # GitHub release asset which the official JRSoftware download
        # page points to instead.
        $InnoVersion = "6.7.3"
        $InnoReleaseTag = "is-6_7_3"

        $InnoDownloadUrl = (
            "https://github.com/jrsoftware/issrc/releases/download/" +
            "$InnoReleaseTag/innosetup-$InnoVersion.exe"
        )

        Write-Host (
            "Downloading official Inno Setup $InnoVersion installer..."
        )

        # Windows PowerShell 5.1 on older Windows images can otherwise
        # negotiate an obsolete TLS version.
        try {
            [Net.ServicePointManager]::SecurityProtocol = `
                [Net.SecurityProtocolType]::Tls12
        }
        catch {
            Write-Warning (
                "Could not force TLS 1.2. Continuing with the " +
                "system default."
            )
        }

        $DownloadHeaders = @{
            "User-Agent" = "Genshin-Mod-Manager-Build"
            "Accept" = "application/octet-stream"
        }

        try {
            Invoke-WebRequest `
                -Uri $InnoDownloadUrl `
                -OutFile $InnoBootstrap `
                -Headers $DownloadHeaders `
                -UseBasicParsing
        }
        catch {
            Write-Warning (
                "Invoke-WebRequest failed. Trying BITS..."
            )

            if (
                Get-Command `
                    -Name "Start-BitsTransfer" `
                    -ErrorAction SilentlyContinue
            ) {
                Start-BitsTransfer `
                    -Source $InnoDownloadUrl `
                    -Destination $InnoBootstrap
            }
            else {
                throw
            }
        }

        if (-not (
            Test-Path -LiteralPath $InnoBootstrap
        )) {
            throw (
                "Inno Setup bootstrap download failed."
            )
        }

        $InnoFile = Get-Item `
            -LiteralPath $InnoBootstrap

        # Avoid PowerShell numeric suffixes here so the script
        # behaves identically on Windows PowerShell 5.1.
        $MinimumInnoInstallerBytes = 5242880

        if (
            $InnoFile.Length -lt
            $MinimumInnoInstallerBytes
        ) {
            $PreviewText = ""

            try {
                $PreviewText = (
                    Get-Content `
                        -LiteralPath $InnoBootstrap `
                        -Raw `
                        -ErrorAction Stop
                )

                if ($PreviewText.Length -gt 200) {
                    $PreviewText = (
                        $PreviewText.Substring(
                            0,
                            200
                        )
                    )
                }
            }
            catch {
                $PreviewText = "<binary or unreadable>"
            }

            throw (
                "Downloaded Inno Setup file is unexpectedly small. " +
                "Size=$($InnoFile.Length) bytes; " +
                "URL=$InnoDownloadUrl; " +
                "Preview=$PreviewText"
            )
        }

        $InnoSignature = Get-AuthenticodeSignature `
            -LiteralPath $InnoBootstrap

        if ($InnoSignature.Status -ne "Valid") {
            throw (
                "Inno Setup Authenticode signature is not valid. " +
                "Status=$($InnoSignature.Status)"
            )
        }

        if (-not $InnoSignature.SignerCertificate) {
            throw (
                "Inno Setup installer has no signer certificate."
            )
        }

        $InnoSigner = $InnoSignature.SignerCertificate.Subject

        if ($InnoSigner -notmatch "Pyrsys B\.V\.") {
            throw (
                "Unexpected Inno Setup signer: " +
                $InnoSigner
            )
        }

        Write-Host "Inno Setup signature: VALID"
        Write-Host "Signer: $InnoSigner"

        if (
            Test-Path -LiteralPath $InnoDirectory
        ) {
            Remove-Item `
                -LiteralPath $InnoDirectory `
                -Recurse `
                -Force
        }

        New-Item `
            -ItemType Directory `
            -Path $InnoDirectory `
            -Force |
            Out-Null

        Write-Host (
            "Installing portable Inno Setup build tools..."
        )

        $InnoProcess = Start-Process `
            -FilePath $InnoBootstrap `
            -ArgumentList @(
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/SP-",
                "/PORTABLE=1",
                "/CURRENTUSER",
                "/DIR=$InnoDirectory"
            ) `
            -Wait `
            -PassThru

        if ($InnoProcess.ExitCode -ne 0) {
            throw (
                "Portable Inno Setup installation failed with exit code " +
                "$($InnoProcess.ExitCode)"
            )
        }

        $ISCC = Get-ChildItem `
            -LiteralPath $InnoDirectory `
            -Filter "ISCC.exe" `
            -File `
            -Recurse |
            Select-Object `
                -ExpandProperty FullName `
                -First 1

        if (-not $ISCC) {
            throw (
                "Portable Inno Setup completed, but ISCC.exe was not found."
            )
        }
    }

    Write-Host (
        "Using local Inno Setup compiler: " +
        $ISCC
    )
}
else {
    Write-Host (
        "Using installed Inno Setup compiler: " +
        $ISCC
    )
}

& $ISCC `
    "/DMyAppVersion=$Version" `
    "$Root\packaging\windows\installer.iss"

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
