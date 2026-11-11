param([switch]$SkipMysql)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
$logs = Join-Path $projectRoot 'data/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
if (!$SkipMysql) { & "$PSScriptRoot/mysql.ps1" }
foreach ($port in @(8000,5173)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is already in use. Stop the existing project services before starting another instance." }
}
$processes = @()
try {
    $apiProcess = Start-Process -FilePath $python -ArgumentList @('-u','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'api.out.log') -RedirectStandardError (Join-Path $logs 'api.err.log') -PassThru
    $processes += @{ name='api'; pid=$apiProcess.Id }
    $workerProcess = Start-Process -FilePath $python -ArgumentList @('-u','-m','app.worker') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'worker.out.log') -RedirectStandardError (Join-Path $logs 'worker.err.log') -PassThru
    $processes += @{ name='worker'; pid=$workerProcess.Id }
    $vite = Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'
    $webProcess = Start-Process -FilePath (Get-Command node).Source -ArgumentList @("`"$vite`"",'--host','127.0.0.1') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'web.out.log') -RedirectStandardError (Join-Path $logs 'web.err.log') -PassThru
    $processes += @{ name='web'; pid=$webProcess.Id }
} finally {
    $processes | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $projectRoot 'data/processes.json')
}
foreach ($url in @('http://127.0.0.1:8000/api/v1/health','http://127.0.0.1:5173')) {
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        try { $response=Invoke-WebRequest -Uri $url -TimeoutSec 2; if ($response.StatusCode -eq 200) {$ready=$true; break} } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (!$ready) { throw "Service did not become ready: $url. See data/logs." }
}
Write-Output 'TicketFlow: http://127.0.0.1:5173'
Write-Output 'API docs: http://127.0.0.1:8000/docs'
Write-Output 'Login: admin; password is ADMIN_PASSWORD in .env (never printed by scripts).'
