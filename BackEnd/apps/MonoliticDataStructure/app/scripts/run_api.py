#!/usr/bin/env python
"""Script para ejecutar la API FastAPI"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import uvicorn
from src.api.main import app

if __name__ == "__main__":
    print("🚀 Iniciando Supply Chain Management API...")
    print(f"📚 Documentación disponible en: http://localhost:8000/docs")
    print(f"📖 Redoc disponible en: http://localhost:8000/redoc")
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )