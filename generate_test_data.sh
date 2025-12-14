#!/bin/bash
# Generar datos de prueba para Analytics

echo "Generando datos de prueba para Analytics..."

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login-json \
    -H 'Content-Type: application/json' \
    -d '{"username": "admin", "password": "123456"}' | \
    python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

# Crear archivos de diferentes tipos
echo "Documento PDF" > /tmp/documento.pdf
echo "Imagen JPG" > /tmp/foto.jpg
echo "Video MP4" > /tmp/video.mp4
echo "Documento Word" > /tmp/informe.docx
echo "Hoja de cálculo" > /tmp/datos.xlsx
echo "Presentación" > /tmp/slides.pptx
echo "Archivo de texto" > /tmp/notas.txt
echo "Código Python" > /tmp/script.py

# Subir archivos con diferentes tags
curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/documento.pdf" \
    -F "tags=documentos,importante,trabajo" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/foto.jpg" \
    -F "tags=imagenes,personal,vacaciones" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/video.mp4" \
    -F "tags=videos,personal,familia" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/informe.docx" \
    -F "tags=documentos,trabajo,reportes" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/datos.xlsx" \
    -F "tags=datos,trabajo,analisis" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/slides.pptx" \
    -F "tags=presentaciones,trabajo,clientes" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/notas.txt" \
    -F "tags=notas,personal" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/script.py" \
    -F "tags=codigo,desarrollo,python" > /dev/null

echo "✅ 8 archivos de prueba subidos"
echo ""
echo "Ahora puedes ver:"
echo "  - Frontend: http://localhost"
echo "  - Analytics: http://localhost → Analytics"
