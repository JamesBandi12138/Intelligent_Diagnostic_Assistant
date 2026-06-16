$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $root "frontend"
$logFile = Join-Path $root "frontend-live.log"

Set-Location $frontendDir
"[$(Get-Date -Format s)] starting frontend on http://127.0.0.1:5173" | Out-File -FilePath $logFile -Encoding utf8 -Append
& npm.cmd run dev -- --host 127.0.0.1 --port 5173 *>> $logFile
