$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$projectRoot = Split-Path $PSScriptRoot -Parent
$mysqlData = Join-Path $projectRoot 'data/mysql'
$mysqlLog = Join-Path $projectRoot 'data/logs/mysql.log'
if (!(Test-Path (Join-Path $mysqlData 'auto.cnf'))) { throw 'Initialize the isolated database first; see README.' }
if (Get-NetTCPConnection -LocalPort 3307 -State Listen -ErrorAction SilentlyContinue) { Write-Output 'Port 3307 is already listening.'; exit 0 }
Start-Process -FilePath 'D:/mysql/bin/mysqld.exe' -WindowStyle Hidden -ArgumentList @('--no-defaults', '--basedir=D:/mysql', "--datadir=`"$mysqlData`"", '--port=3307', '--bind-address=127.0.0.1', '--mysqlx=0', "--log-error=`"$mysqlLog`"")
