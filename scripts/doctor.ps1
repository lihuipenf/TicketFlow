$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
Write-Output "Project: $projectRoot"
if (!(Test-Path $python)) { throw 'Python virtual environment missing. See README setup instructions.' }
& $python --version
node --version
Write-Output "TEMP: $env:TEMP"
Write-Output "Model cache: $env:HF_HOME"
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $python -c "from sqlalchemy import text; from app.db import engine; from app.config import settings; c=engine.connect(); print('MySQL:',c.scalar(text('SELECT VERSION()'))); c.close(); print('LLM configured:',bool(settings().llm_api_key.get_secret_value())); print('Model:',settings().llm_model)"
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency check failed.' }
} finally { Pop-Location }
