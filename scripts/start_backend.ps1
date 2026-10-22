param([switch]$Restart, [switch]$StopOnly)
$ErrorActionPreference='Stop'
$workspaceRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonPath=Join-Path $workspaceRoot '.venv\Scripts\python.exe'
$runtimePath=Join-Path $workspaceRoot 'runtime'
$pidPath=Join-Path $runtimePath 'backend.pid'
if (Test-Path -LiteralPath $pidPath) {
    $backendProcessId=[int](Get-Content -LiteralPath $pidPath)
    $backendProcess=Get-CimInstance Win32_Process -Filter "ProcessId = $backendProcessId"
    if ($backendProcess) {
        if ($backendProcess.ExecutablePath -ne $pythonPath -or -not $backendProcess.CommandLine.Contains('backend.main:app')) { throw 'Recorded process is not the project backend; refusing to change it.' }
        if (-not ($Restart -or $StopOnly)) { Write-Output 'FinSentry is already running. Use -Restart to load changes.'; exit 0 }
        try {
            $pending=@(Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v2/investigations?limit=100' -TimeoutSec 5) | Where-Object { $_.status -in @('QUEUED','RUNNING') }
            if ($pending) { throw 'Wait until current investigations finish before restarting.' }
        } catch {
            if ($_.Exception.Message -like '*current investigations*') { throw }
            Write-Output 'Existing API did not respond; restarting the verified project process.'
        }
        Stop-Process -Id $backendProcessId
        Wait-Process -Id $backendProcessId -ErrorAction SilentlyContinue
    }
}
if ($StopOnly) { exit 0 }
$backendProcess=Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--workers','1') `
    -WorkingDirectory $workspaceRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'backend-out.log') `
    -RedirectStandardError (Join-Path $runtimePath 'backend-error.log') -PassThru
Set-Content -LiteralPath $pidPath -Value $backendProcess.Id
for ($attempt=0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($backendProcess.HasExited) { throw 'Backend exited; inspect runtime/backend-error.log.' }
    try {
        $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v2/health' -TimeoutSec 3
        if ($health.status -eq 'ready') { Write-Output 'FinSentry analyst workspace ready: http://127.0.0.1:8000'; exit 0 }
    } catch { }
}
throw 'Backend readiness timed out; inspect runtime/backend-error.log.'
