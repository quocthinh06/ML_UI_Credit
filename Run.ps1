$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $env:USERPROFILE '.creditrisk-ai\venv\Scripts\python.exe'
if ($env:CREDITRISK_PYTHON) { $pythonPath = $env:CREDITRISK_PYTHON }
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host 'Run Setup.ps1 first.'
    exit 1
}
& $pythonPath desktop_main.py
exit $LASTEXITCODE
