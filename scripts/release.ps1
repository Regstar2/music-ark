[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Version
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Version -notmatch '^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$') {
    throw "Release version must be an exact vMAJOR.MINOR.PATCH tag, got '$Version'."
}

$plainVersion = $Version.Substring(1)
$sourceVersion = (Get-Content -LiteralPath '.\VERSION' -Raw).Trim()
if ($sourceVersion -ne $plainVersion) {
    throw "Tag/source version mismatch: tag=$plainVersion VERSION=$sourceVersion"
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Windows Python launcher 'py' is required."
}
& py -3.12 --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.12 is required for the release packaging runtime.'
}

Write-Host "Building MusicArk $Version final Windows artifacts..."
& .\tools\package_windows.ps1 -PythonVersion '3.12'
if ($LASTEXITCODE -ne 0) {
    throw 'MusicArk packaging failed.'
}

$artifactDir = Join-Path $root "artifacts\v$plainVersion"
$portable = Join-Path $artifactDir "MusicArk-$plainVersion-win-x64.zip"
$installer = Join-Path $artifactDir "MusicArk-Setup-$plainVersion-x64.exe"
$checksums = Join-Path $artifactDir 'SHA256SUMS.txt'

foreach ($required in @($portable, $installer, $checksums)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required release artifact is missing: $required"
    }
}

$dist = Join-Path $root 'dist'
if (Test-Path -LiteralPath $dist) {
    Remove-Item -LiteralPath $dist -Recurse -Force
}
New-Item -ItemType Directory -Path $dist | Out-Null

Copy-Item -LiteralPath $portable -Destination $dist
Copy-Item -LiteralPath $installer -Destination $dist
Copy-Item -LiteralPath $checksums -Destination $dist

$assetBase = "https://github.com/Regstar2/music-ark/releases/download/$Version"
$notesUrl = "https://github.com/Regstar2/music-ark/releases/tag/$Version"
$manifest = Join-Path $dist 'update-manifest.json'

& py -3.12 .\tools\generate_update_manifest.py `
    $installer `
    --version $plainVersion `
    --channel stable `
    --asset-base-url $assetBase `
    --release-notes-url $notesUrl `
    --output $manifest
if ($LASTEXITCODE -ne 0) {
    throw 'Stable update manifest generation failed.'
}

Write-Host 'Final release artifacts:'
Get-ChildItem -LiteralPath $dist -File | Select-Object Name, Length, LastWriteTime
