"""Configuración de la API"""

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # Base de datos
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "admin"
    DB_PASSWORD: str = "admin123"
    DB_NAME: str = "supply_chain"
    
    # API
    API_TITLE: str = "Supply Chain Management API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "API para gestión de stock y cadena de suministro"
    
    # Seguridad
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorar campos no definidos

settings = Settings()

# Configuración de la base de datos (fuera de la clase)
DATABASE_URL = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"