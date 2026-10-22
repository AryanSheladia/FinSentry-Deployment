param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $workspaceRoot
$pythonPath = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project environment is missing. Follow README setup first.' }
if (-not (Test-Path -LiteralPath (Join-Path $workspaceRoot 'models\sparkov_v2\pipeline.joblib')) -or -not (Test-Path -LiteralPath (Join-Path $workspaceRoot 'runtime\sparkov\history.sqlite'))) { throw 'Train Sparkov v2 first: .\.venv\Scripts\python.exe -m backend.ml.sparkov_train' }
if ($Rebuild -or -not (Test-Path -LiteralPath (Join-Path $workspaceRoot 'frontend\dist\index.html'))) {
    Push-Location -LiteralPath (Join-Path $workspaceRoot 'frontend')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            $env:npm_config_cache = Join-Path $workspaceRoot 'runtime\npm-cache'
            & npm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
& $pythonPath (Join-Path $PSScriptRoot 'local_mysql.py') start
if ($LASTEXITCODE -ne 0) { throw 'Project MySQL startup failed.' }
& (Join-Path $PSScriptRoot 'start_backend.ps1') -Restart
Write-Output 'Open FinSentry: http://127.0.0.1:8000'
