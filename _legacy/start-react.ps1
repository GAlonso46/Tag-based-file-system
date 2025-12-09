# Script para iniciar API Backend + Frontend React

Write-Host "🚀 Iniciando Tag-Based File System (React Version)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si Python está instalado
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python no está instalado" -ForegroundColor Red
    exit 1
}

# Verificar si Node/Yarn está instalado
if (-not (Get-Command yarn -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host "❌ Node.js/Yarn no está instalado" -ForegroundColor Red
        exit 1
    }
    Write-Host "⚠️  Yarn no encontrado, usando npm" -ForegroundColor Yellow
    $packageManager = "npm"
} else {
    $packageManager = "yarn"
}

Write-Host "📦 Gestor de paquetes: $packageManager" -ForegroundColor Green
Write-Host ""

# Iniciar Backend API en nueva ventana
Write-Host "🔧 Iniciando Backend API..." -ForegroundColor Yellow
$apiProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python run_api.py" -PassThru

# Esperar 3 segundos para que el API inicie
Start-Sleep -Seconds 3

# Iniciar Frontend React en nueva ventana
Write-Host "⚛️  Iniciando Frontend React..." -ForegroundColor Yellow
if ($packageManager -eq "yarn") {
    $frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend-react'; yarn dev" -PassThru
} else {
    $frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend-react'; npm run dev" -PassThru
}

Write-Host ""
Write-Host "✅ Aplicación iniciada!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Backend API:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "📍 Frontend:     http://localhost:5173" -ForegroundColor Cyan
Write-Host "📍 API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Para detener: Cierra las ventanas de PowerShell" -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona cualquier tecla para salir de este script..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
