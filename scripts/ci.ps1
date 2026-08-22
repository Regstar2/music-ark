[CmdletBinding()]
param(
    [switch]$SkipPackageSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Write-Host '=== MusicArk trusted CI ==='
Write-Host "Root: $root"

$pythonVersion = (& (Join-Path $PSScriptRoot 'resolve-python.ps1')).Trim()
if (-not $pythonVersion) {
    throw 'Python resolver returned an empty version.'
}
$pythonArg = "-$pythonVersion"
Write-Host "Trusted CI Python: $pythonVersion"

Write-Host 'Installing MusicArk test dependencies...'
& py $pythonArg -m pip install --disable-pip-version-check -e . -r requirements-yandex.txt
Assert-LastExitCode 'Python dependency installation'

# CI is always offline/fail-closed for provider mutations. A real-account/live
# acceptance test must use a separate explicit manual procedure.
foreach ($name in @(
    'MUSICARK_YANDEX_UPLOAD_LIVE',
    'MUSICARK_YANDEX_PLAYLIST_LIVE',
    'YANDEX_MUSIC_TOKEN'
)) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

Write-Host 'Staging the pinned imageio-ffmpeg executable used by conversion tests...'
$ffmpegStage = Join-Path $root '.tools\ffmpeg\ffmpeg.exe'
$env:MUSICARK_FFMPEG_STAGED_PATH = $ffmpegStage
$ffmpeg = (& py $pythonArg -c "import imageio_ffmpeg, os, pathlib, shutil; src=pathlib.Path(imageio_ffmpeg.get_ffmpeg_exe()); dst=pathlib.Path(os.environ['MUSICARK_FFMPEG_STAGED_PATH']); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); print(dst.resolve())").Trim()
Assert-LastExitCode 'FFmpeg staging'
if (-not (Test-Path -LiteralPath $ffmpeg -PathType Leaf)) {
    throw "FFmpeg was not staged correctly: $ffmpeg"
}
$env:MUSICARK_FFMPEG_PATH = (Resolve-Path -LiteralPath $ffmpeg).Path
Remove-Item Env:MUSICARK_FFMPEG_STAGED_PATH -ErrorAction SilentlyContinue
& $env:MUSICARK_FFMPEG_PATH -version
Assert-LastExitCode 'FFmpeg smoke'

Write-Host 'Checking version consistency...'
& py $pythonArg tools/check_version_consistency.py
Assert-LastExitCode 'Version consistency'

Write-Host 'Running the complete Python regression suite...'
& py $pythonArg -m unittest discover -s tests -p 'test_*.py' -v
Assert-LastExitCode 'Python regression suite'

Write-Host 'Generating deterministic v0.14 performance evidence...'
$performanceDir = Join-Path $root '.musicark\performance'
New-Item -ItemType Directory -Path $performanceDir -Force | Out-Null
& py $pythonArg .\tools\performance_smoke.py --output .\.musicark\performance\release-regression.json
Assert-LastExitCode 'Performance smoke'
& py $pythonArg .\tools\sqlite_query_audit.py --output .\.musicark\performance\sqlite-query-audit.json
Assert-LastExitCode 'SQLite query audit'

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw 'Flutter is required on the trusted Windows runner.'
}

Push-Location (Join-Path $root 'ui\musicark_ui')
try {
    Write-Host 'Resolving Flutter dependencies...'
    & flutter pub get
    Assert-LastExitCode 'flutter pub get'

    Write-Host 'Running Flutter analyzer...'
    & flutter analyze --no-fatal-infos
    Assert-LastExitCode 'flutter analyze'

    Write-Host 'Running the complete Flutter test suite...'
    & flutter test
    Assert-LastExitCode 'flutter test'

    Write-Host 'Building Flutter Windows application...'
    & flutter build windows
    Assert-LastExitCode 'flutter build windows'
}
finally {
    Pop-Location
}

if (-not $SkipPackageSmoke) {
    Write-Host "Building the portable v0.15+ standalone package smoke with Python $pythonVersion..."
    & .\tools\package_windows.ps1 -SkipInstaller -PythonVersion $pythonVersion
    Assert-LastExitCode 'Portable package smoke'
}
else {
    Write-Host 'Package smoke skipped by caller; release.ps1 will build final artifacts.'
}

Write-Host '=== MusicArk trusted CI passed ==='
