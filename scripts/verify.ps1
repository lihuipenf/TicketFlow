$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
} finally { Pop-Location }
Push-Location (Join-Path $projectRoot 'frontend')
try {
    npm test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    npm audit --audit-level=moderate
    if ($LASTEXITCODE -ne 0) { throw 'Dependency audit failed.' }
} finally { Pop-Location }
Write-Output 'All verification commands passed.'
