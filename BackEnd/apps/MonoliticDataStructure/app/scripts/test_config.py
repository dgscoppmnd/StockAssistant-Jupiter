"""Script para probar la configuración de la API"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.api.config import settings, DATABASE_URL

print("="*50)
print("🔧 CONFIGURACIÓN DE LA API")
print("="*50)

print(f"✅ DB_HOST: {settings.DB_HOST}")
print(f"✅ DB_PORT: {settings.DB_PORT}")
print(f"✅ DB_USER: {settings.DB_USER}")
print(f"✅ DB_NAME: {settings.DB_NAME}")
print(f"✅ API_TITLE: {settings.API_TITLE}")
print(f"✅ API_VERSION: {settings.API_VERSION}")
print(f"✅ DATABASE_URL: {DATABASE_URL}")
print(f"✅ ALLOWED_ORIGINS: {settings.ALLOWED_ORIGINS}")

print("="*50)
print("✅ Configuración cargada correctamente!")