$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$stateFile = Join-Path $projectRoot 'data/processes.json'
if (!(Test-Path $stateFile)) { Write-Output 'No recorded TicketFlow processes.'; exit 0 }
$records = Get-Content -Raw $stateFile | ConvertFrom-Json
foreach ($record in $records) {
    $ownedProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)" -ErrorAction SilentlyContinue
    if (!$ownedProcess) { continue }
    if (!$ownedProcess.CommandLine.Contains($projectRoot)) { Write-Warning "PID $($record.pid) no longer belongs to this project; skipped."; continue }
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($record.pid)"
    foreach ($child in $children) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
    Stop-Process -Id $record.pid -ErrorAction SilentlyContinue
}
Write-Output 'TicketFlow API, Worker and frontend stopped. MySQL and all data retained.'
