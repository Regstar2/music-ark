[CmdletBinding()]
param(
    [string[]]$Candidates = @('3.13', '3.12', '3.11', '3.10')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Windows Python launcher 'py' is required."
}

foreach ($version in $Candidates) {
    Write-Host "Checking Python $version..."

    & py "-$version" -c "import ctypes, pip, venv, sys; assert sys.version_info >= (3, 10)" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Selected healthy Python $version."
        Write-Output $version
        return
    }

    Write-Host "Python $version is unavailable or unhealthy; trying the next supported version."
}

throw "No healthy supported Python installation was found. Expected one of: $($Candidates -join ', ')."
