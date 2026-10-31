$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$runtimePath = Join-Path $env:USERPROFILE '.creditrisk-ai\venv'
$pythonPath = Join-Path $runtimePath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv $runtimePath
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11/3.12 is required.' }
}
& $pythonPath -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $pythonPath tools/download_model.py
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
if (-not (Test-Path -LiteralPath 'config.local.json')) {
    Copy-Item -LiteralPath 'config.example.json' -Destination 'config.local.json'
    Write-Host 'Edit config.local.json with your MySQL account before starting.'
}
Write-Host 'Setup complete. Start with Run.cmd.'
