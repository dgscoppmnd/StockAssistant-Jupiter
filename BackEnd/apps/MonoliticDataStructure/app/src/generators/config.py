"""Configuración para la generación de datos"""

import os
from pathlib import Path
from typing import Optional, List

# =============================================
# RUTAS DE DIRECTORIOS
# =============================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
GENERATED_DATA_DIR = DATA_DIR / "generated"

# Crear directorios si no existen
GENERATED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# =============================================
# ARCHIVOS
# =============================================

KAGGLE_CSV = RAW_DATA_DIR / "Kaggle_Dataset.csv"

OUTPUT_FILES = {
    "products": GENERATED_DATA_DIR / "products.csv",
    "suppliers": GENERATED_DATA_DIR / "suppliers.csv",
    "warehouses": GENERATED_DATA_DIR / "warehouses.csv",
    "inventory": GENERATED_DATA_DIR / "inventory.csv",
    "sales": GENERATED_DATA_DIR / "sales.csv",
    "logistics": GENERATED_DATA_DIR / "logistics.csv",
    "metrics": GENERATED_DATA_DIR / "supply_chain_metrics.csv"
}

# =============================================
# CONFIGURACIÓN DE GENERACIÓN
# =============================================

BATCH_SIZE = 1000
SEED: Optional[int] = 42  # Para reproducibilidad

# =============================================
# OPCIONES PARA CAMPOS CATEGÓRICOS
# =============================================

PRODUCT_CATEGORIES = ["Electronics", "Fashion", "Home", "Food", "Beauty", "Sports", "Toys", "Books"]
BRANDS = ["BrandA", "BrandB", "BrandC", "BrandD", "BrandE"]
TRANSPORTATION_MODES = ["Road", "Air", "Sea", "Rail"]
WAREHOUSE_LOCATIONS = ["North", "South", "East", "West", "Central"]