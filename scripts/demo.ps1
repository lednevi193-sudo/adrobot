param([ValidateRange(1024, 65535)][int]$Port = 8001)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$demoPython = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    throw 'Сначала установите зависимости бэкенда по README (backend\.venv).'
}
Push-Location $repoRoot
try {
    & npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Сборка фронтенда не удалась.' }
    Write-Host "Demo: http://127.0.0.1:$Port — 3 оффера, кампании на 2 и 3 оффера."
    Write-Host 'Остановка: Ctrl+C. Перезапуск сбросит демоданные.'
    & $demoPython -m uvicorn app.demo:create_demo_app --factory --app-dir backend --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось запустить демосервер.' }
}
finally { Pop-Location }
