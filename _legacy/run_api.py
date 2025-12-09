"""
Script para ejecutar el servidor API
"""
import uvicorn

if __name__ == "__main__":
    print("🚀 Iniciando Tag-Based File System API...")
    print("📡 API disponible en: http://localhost:8000")
    print("📚 Documentación en: http://localhost:8000/docs")
    print("\nPresiona Ctrl+C para detener el servidor\n")
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload en desarrollo
        log_level="info"
    )
