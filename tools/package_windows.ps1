[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
if ($version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$') {
    throw "VERSION must contain strict MAJOR.MINOR.PATCH SemVer."
}

$buildRoot = Join-Path $root ".build\v015"
$artifactDir = Join-Path $root "artifacts\v$version"
$stage = Join-Path $buildRoot "MusicArk"
$appExeName = "Music Ark.exe"
$flutterExeName = "musicark_ui.exe"
$venv = Join-Path $buildRoot "build-venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $artifactDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $buildRoot, $artifactDir, $stage -Force | Out-Null

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Windows Python launcher 'py' is required to build the frozen backend runtime."
}

& py "-$PythonVersion" -c "import sys; print(sys.version)"
if ($LASTEXITCODE -ne 0) {
    throw "Python $PythonVersion is required for the packaging runtime."
}
& py "-$PythonVersion" -m venv $venv
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "Could not create the packaging virtual environment."
}

& $venvPython -m pip install --disable-pip-version-check --no-cache-dir --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update pip in the packaging environment." }
& $venvPython -m pip install --disable-pip-version-check --no-cache-dir -e . -r requirements-yandex.txt "pyinstaller==6.16.0"
if ($LASTEXITCODE -ne 0) { throw "Could not install MusicArk packaging dependencies." }

& $venvPython tools/check_version_consistency.py
if ($LASTEXITCODE -ne 0) { throw "Version consistency check failed." }

Push-Location (Join-Path $root "ui\musicark_ui")
try {
    & flutter pub get
    if ($LASTEXITCODE -ne 0) { throw "flutter pub get failed." }
    & flutter build windows --release
    if ($LASTEXITCODE -ne 0) { throw "Flutter Windows release build failed." }
} finally {
    Pop-Location
}

$flutterOutput = Join-Path $root "ui\musicark_ui\build\windows\x64\runner\Release"
$flutterExe = Join-Path $flutterOutput $flutterExeName
if (-not (Test-Path -LiteralPath $flutterExe -PathType Leaf)) {
    throw "Flutter release executable was not found at $flutterExe."
}
Copy-Item -Path (Join-Path $flutterOutput "*") -Destination $stage -Recurse -Force
$stagedFlutterExe = Join-Path $stage $flutterExeName
$stagedAppExe = Join-Path $stage $appExeName
if (-not (Test-Path -LiteralPath $stagedFlutterExe -PathType Leaf)) {
    throw "Staged Flutter executable was not found at $stagedFlutterExe."
}
Move-Item -LiteralPath $stagedFlutterExe -Destination $stagedAppExe -Force

$runtimeDist = Join-Path $buildRoot "runtime-dist"
$runtimeWork = Join-Path $buildRoot "runtime-work"
$runtimeSpec = Join-Path $buildRoot "runtime-spec"
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name python `
    --distpath $runtimeDist `
    --workpath $runtimeWork `
    --specpath $runtimeSpec `
    --collect-all imageio_ffmpeg `
    --collect-all keyring `
    --collect-all yandex_music `
    --collect-submodules httpx `
    --collect-submodules socksio `
    src\musicark\runtime_cli.py
if ($LASTEXITCODE -ne 0) { throw "Frozen MusicArk backend runtime build failed." }

$runtimeSource = Join-Path $runtimeDist "python"
$runtimeTarget = Join-Path $stage ".venv\Scripts"
New-Item -ItemType Directory -Path $runtimeTarget -Force | Out-Null
Copy-Item -Path (Join-Path $runtimeSource "*") -Destination $runtimeTarget -Recurse -Force
$runtimeExe = Join-Path $runtimeTarget "python.exe"
if (-not (Test-Path -LiteralPath $runtimeExe -PathType Leaf)) {
    throw "Packaged backend runtime executable is missing."
}

# Compatibility sentinels let legacy Dart bridge discovery identify the
# packaged application root without shipping a development checkout. The
# frozen runtime ignores these files and rewrites --base-dir to per-user data.
Set-Content -LiteralPath (Join-Path $stage "pyproject.toml") -Value "# MusicArk packaged runtime sentinel" -Encoding utf8
$sentinels = @(
    "src\musicark\__init__.py",
    "src\musicark\mvp_bridge.py",
    "src\musicark\platform_bridge.py",
    "src\musicark\content_labels\bridge.py",
    "src\musicark\download\bridge.py",
    "src\musicark\external_metadata\bridge.py",
    "src\musicark\metadata\bridge.py",
    "src\musicark\recovery\bridge.py",
    "src\musicark\sync\bridge.py",
    "src\musicark\upload\bridge.py",
    "src\musicark\variant\acceptance_bridge.py"
)
foreach ($relative in $sentinels) {
    $path = Join-Path $stage $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
    Set-Content -LiteralPath $path -Value "# packaged runtime sentinel" -Encoding utf8
}

& $runtimeExe --version
if ($LASTEXITCODE -ne 0) { throw "Packaged backend runtime --version smoke failed." }
$feedbackSmoke = (& $runtimeExe -m musicark.feedback_bridge link --kind bug | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "Packaged feedback bridge smoke failed." }
$feedbackJson = $feedbackSmoke | ConvertFrom-Json
if (-not $feedbackJson.url -or $feedbackJson.kind -ne "bug") {
    throw "Packaged feedback bridge returned an invalid payload."
}

$portable = Join-Path $artifactDir "MusicArk-$version-win-x64.zip"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archiveAttempts = 4
$archiveCreated = $false
for ($attempt = 1; $attempt -le $archiveAttempts; $attempt++) {
    Remove-Item -LiteralPath $portable -Force -ErrorAction SilentlyContinue
    try {
        Write-Host "Creating portable ZIP (attempt $attempt/$archiveAttempts)..."
        [System.IO.Compression.ZipFile]::CreateFromDirectory(
            $stage,
            $portable,
            [System.IO.Compression.CompressionLevel]::Optimal,
            $false
        )
        if (-not (Test-Path -LiteralPath $portable -PathType Leaf)) {
            throw "Portable ZIP was not created."
        }
        if ((Get-Item -LiteralPath $portable).Length -le 0) {
            throw "Portable ZIP is empty."
        }
        $archiveCreated = $true
        break
    } catch {
        Remove-Item -LiteralPath $portable -Force -ErrorAction SilentlyContinue
        if ($attempt -ge $archiveAttempts) {
            throw "Portable ZIP creation failed after $archiveAttempts attempts: $($_.Exception.Message)"
        }
        $delaySeconds = 2 * $attempt
        Write-Warning "Portable ZIP creation hit a temporary file-access error. Retrying in $delaySeconds second(s): $($_.Exception.Message)"
        Start-Sleep -Seconds $delaySeconds
    }
}
if (-not $archiveCreated) {
    throw "Portable ZIP creation did not complete."
}

if (-not $SkipInstaller) {
    $isccCandidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
    $iscc = $isccCandidates | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 compiler (ISCC.exe) is required. Re-run with -SkipInstaller only for non-release packaging smoke."
    }
    & $iscc "/Qp" "/DMyAppVersion=$version" "/DSourceDir=$stage" "/DOutputDir=$artifactDir" (Join-Path $root "packaging\windows\MusicArk.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
}

$hashTargets = Get-ChildItem -LiteralPath $artifactDir -File | Where-Object { $_.Extension -in @('.zip', '.exe') }
if (-not $hashTargets) {
    throw "No release artifacts were created for hashing."
}
$hashLines = foreach ($file in $hashTargets) {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    "$hash  $($file.Name)"
}
$hashFile = Join-Path $artifactDir "SHA256SUMS.txt"
$hashLines | Set-Content -LiteralPath $hashFile -Encoding ascii

if (-not (Test-Path -LiteralPath $portable -PathType Leaf)) {
    throw "Portable ZIP disappeared before packaging completion."
}
if (-not (Test-Path -LiteralPath $hashFile -PathType Leaf)) {
    throw "SHA256SUMS.txt was not created."
}

Write-Host "MusicArk Windows packaging complete: $artifactDir"
Get-ChildItem -LiteralPath $artifactDir -File | Select-Object Name, Length, LastWriteTime
