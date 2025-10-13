# Script PowerShell para construir imágenes Docker

Write-Host "🐳 Construyendo imágenes Docker..." -ForegroundColor Cyan

# Backend
Write-Host "`n📦 Construyendo Backend..." -ForegroundColor Yellow
docker build -f Dockerfile.backend -t tagfs-backend:latest .

# Frontend
Write-Host "`n🎨 Construyendo Frontend..." -ForegroundColor Yellow
Set-Location frontend-react
docker build -t tagfs-frontend:latest .
Set-Location ..

# Verificar
Write-Host "`n✅ Imágenes construidas:" -ForegroundColor Green
docker images | Select-String "tagfs"

Write-Host "`n🎉 ¡Listo! Ahora puedes:" -ForegroundColor Green
Write-Host "   - Desarrollo local: docker-compose up" -ForegroundColor White
Write-Host "   - Docker Swarm: docker stack deploy -c docker-stack.yml tagfs" -ForegroundColor White
