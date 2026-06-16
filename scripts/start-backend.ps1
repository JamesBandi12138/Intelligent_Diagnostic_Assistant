$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$pythonExe = Join-Path $root ".venv\\Scripts\\python.exe"
$logFile = Join-Path $root "backend-live.log"

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found: $pythonExe"
}

Set-Location $backendDir
"[$(Get-Date -Format s)] starting backend on http://127.0.0.1:8000" | Out-File -FilePath $logFile -Encoding utf8 -Append
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 *>> $logFile
