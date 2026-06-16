$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$pythonExe = Join-Path $root ".venv\\Scripts\\python.exe"
$backendLog = Join-Path $root "backend-live.log"
$frontendLog = Join-Path $root "frontend-live.log"

$backend = Start-Process `
    -FilePath $pythonExe `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendLog `
    -ArgumentList @(
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    )

$frontend = Start-Process `
    -FilePath "npm.cmd" `
    -WorkingDirectory $frontendDir `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendLog `
    -ArgumentList @(
        "run", "dev",
        "--",
        "--host", "127.0.0.1",
        "--port", "5173"
    )

$pidDir = Join-Path $root ".runtime"
New-Item -ItemType Directory -Force -Path $pidDir | Out-Null

$backend.Id | Out-File -FilePath (Join-Path $pidDir "backend.pid") -Encoding ascii
$frontend.Id | Out-File -FilePath (Join-Path $pidDir "frontend.pid") -Encoding ascii

Write-Output "Backend PID: $($backend.Id)"
Write-Output "Frontend PID: $($frontend.Id)"
