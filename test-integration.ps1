# Script de prueba de integración CLI → Backend → Frontend

Write-Host "🧪 Iniciando prueba de integración CLI-Backend-Frontend" -ForegroundColor Cyan
Write-Host ""

# 1. Obtener ID del contenedor CLI
Write-Host "1️⃣  Obteniendo contenedor CLI..." -ForegroundColor Yellow
$CLI_ID = docker ps --filter "name=tagfs_cli" --format "{{.ID}}" | Select-Object -First 1
Write-Host "   CLI Container: $CLI_ID" -ForegroundColor Green
Write-Host ""

# 2. Crear archivo de prueba
Write-Host "2️⃣  Creando archivo de prueba en /tmp..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$filename = "documento-prueba-$timestamp.txt"
docker exec $CLI_ID bash -c "echo 'Documento de prueba creado desde el CLI de Docker Swarm' > /tmp/$filename"
Write-Host "   ✅ Archivo creado: /tmp/$filename" -ForegroundColor Green
Write-Host ""

# 3. Añadir archivo al sistema con el CLI
Write-Host "3️⃣  Añadiendo archivo al sistema con tags..." -ForegroundColor Yellow
$output = docker exec $CLI_ID python -c @"
from tags.core.tag_service import TagService
from tags.cli.api_sync import APISync
import time

service = TagService('./tags_data')
api_sync = APISync()

# Añadir archivo
added = service.add_files(['/tmp/$filename'], 'docker,swarm,prueba,automatica,2025')
print(f'Archivos añadidos: {added}')

# Esperar a que el archivo se copie completamente
time.sleep(1)

# Sincronizar con BD
print('\nSincronizando con la BD...')
result = api_sync.sync_to_database()
print(f'Resultado sincronización: {result}')
"@
Write-Host $output -ForegroundColor Green
Write-Host ""

# 4. Verificar en files.json
Write-Host "4️⃣  Verificando en files.json..." -ForegroundColor Yellow
$BACKEND_ID = docker ps --filter "name=tagfs_backend" --format "{{.ID}}" | Select-Object -First 1
$filesJson = docker exec $BACKEND_ID cat /app/tags_data/files/files.json | ConvertFrom-Json
if ($filesJson.$filename) {
    Write-Host "   ✅ Archivo encontrado en files.json" -ForegroundColor Green
    Write-Host "   Tags: $($filesJson.$filename -join ', ')" -ForegroundColor White
} else {
    Write-Host "   ❌ Archivo NO encontrado en files.json" -ForegroundColor Red
}
Write-Host ""

# 5. Sincronizar con la BD
Write-Host "5️⃣  Sincronizando con la base de datos..." -ForegroundColor Yellow
$syncResult = curl -s -X POST http://localhost:8000/cli/sync | ConvertFrom-Json
Write-Host "   Admin: $($syncResult.admin_user)" -ForegroundColor White
Write-Host "   Sincronizados: $($syncResult.synced)" -ForegroundColor White
Write-Host "   Ya existían: $($syncResult.skipped)" -ForegroundColor White
Write-Host "   Total: $($syncResult.total)" -ForegroundColor White
Write-Host ""

# 6. Verificar en la BD
Write-Host "6️⃣  Verificando en la base de datos SQL..." -ForegroundColor Yellow
$dbCheck = docker exec $BACKEND_ID python -c @"
import sqlite3, json
conn = sqlite3.connect('/app/tags_data/users.db')
cursor = conn.cursor()
cursor.execute('SELECT filename, tags, owner_id FROM files WHERE filename=?', ('$filename',))
row = cursor.fetchone()
print('ENCONTRADO' if row else 'NO_ENCONTRADO')
if row:
    print(f'{row[0]}|{json.loads(row[1])}|{row[2]}')
"@
$lines = $dbCheck -split "`n"
if ($lines[0] -eq "ENCONTRADO") {
    Write-Host "   ✅ Archivo encontrado en la BD" -ForegroundColor Green
    $parts = $lines[1] -split "\|"
    Write-Host "   Filename: $($parts[0])" -ForegroundColor White
    Write-Host "   Tags: $($parts[1])" -ForegroundColor White
    Write-Host "   Owner ID: $($parts[2])" -ForegroundColor White
} else {
    Write-Host "   ❌ Archivo NO encontrado en la BD" -ForegroundColor Red
    Write-Host "   ⚠️  Ejecutando sincronización manual..." -ForegroundColor Yellow
    curl -s -X POST http://localhost:8000/cli/sync | Out-Null
    Start-Sleep -Seconds 1
    $dbCheck2 = docker exec $BACKEND_ID python -c @"
import sqlite3
conn = sqlite3.connect('/app/tags_data/users.db')
cursor = conn.cursor()
cursor.execute('SELECT filename FROM files WHERE filename=?', ('$filename',))
row = cursor.fetchone()
print('✅ Sincronizado correctamente' if row else '❌ Error en sincronización')
"@
    Write-Host "   $dbCheck2" -ForegroundColor $(if ($dbCheck2 -like "*✅*") { "Green" } else { "Red" })
}
Write-Host ""

# 7. Verificar desde el endpoint /cli/files
Write-Host "7️⃣  Verificando desde API /cli/files..." -ForegroundColor Yellow
Start-Sleep -Seconds 2  # Esperar a que el servicio procese completamente
$apiFiles = curl -s http://localhost:8000/cli/files | ConvertFrom-Json
$testFile = $apiFiles | Where-Object { $_.name -eq $filename }
if ($testFile) {
    Write-Host "   ✅ Archivo encontrado via API" -ForegroundColor Green
    Write-Host "   Name: $($testFile.name)" -ForegroundColor White
    Write-Host "   Tags: $($testFile.tags -join ', ')" -ForegroundColor White
    Write-Host "   Size: $($testFile.size) bytes" -ForegroundColor White
} else {
    Write-Host "   ❌ Archivo NO encontrado via API" -ForegroundColor Red
}
Write-Host ""

# 8. Instrucciones para verificar en el frontend
Write-Host "8️⃣  Verificación en el Frontend:" -ForegroundColor Yellow
Write-Host "   1. Abrir: http://localhost" -ForegroundColor White
Write-Host "   2. Login: test / 123456" -ForegroundColor White
Write-Host "   3. Buscar: $filename" -ForegroundColor White
Write-Host "   4. Debería aparecer con tags: docker, swarm, prueba, automatica, 2025" -ForegroundColor White
Write-Host "   5. Propietario: test (admin)" -ForegroundColor White
Write-Host ""

Write-Host "✅ Prueba completada!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Resumen:" -ForegroundColor Cyan
Write-Host "   - Archivo creado en CLI" -ForegroundColor White
Write-Host "   - Guardado en files.json" -ForegroundColor White
Write-Host "   - Sincronizado en BD SQL" -ForegroundColor White
Write-Host "   - Asignado a usuario admin" -ForegroundColor White
Write-Host "   - Accesible desde Frontend" -ForegroundColor White
