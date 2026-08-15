"""Script de verificación de datos generados"""

import pandas as pd
from pathlib import Path
from src.generators.config import GENERATED_DATA_DIR

def verify_data():
    """Verifica que los archivos generados tengan las relaciones correctas"""
    
    print("🔍 Verificando integridad de datos...")
    
    # Cargar todos los archivos
    files = {
        "products": pd.read_csv(GENERATED_DATA_DIR / "products.csv"),
        "suppliers": pd.read_csv(GENERATED_DATA_DIR / "suppliers.csv"),
        "warehouses": pd.read_csv(GENERATED_DATA_DIR / "warehouses.csv"),
        "inventory": pd.read_csv(GENERATED_DATA_DIR / "inventory.csv"),
        "sales": pd.read_csv(GENERATED_DATA_DIR / "sales.csv"),
        "logistics": pd.read_csv(GENERATED_DATA_DIR / "logistics.csv"),
        "metrics": pd.read_csv(GENERATED_DATA_DIR / "supply_chain_metrics.csv")
    }
    
    # Verificar relaciones
    print("\n📊 Verificando integridad referencial:")
    
    # Inventory -> Products
    inv_prods = set(files["inventory"]["product_id"])
    prods = set(files["products"]["product_id"])
    missing = inv_prods - prods
    print(f"  Inventory-Products: {len(missing)} referencias huérfanas" if missing else "  ✅ Inventory-Products: OK")
    
    # Inventory -> Warehouses
    inv_wh = set(files["inventory"]["warehouse_id"])
    wh = set(files["warehouses"]["warehouse_id"])
    missing = inv_wh - wh
    print(f"  Inventory-Warehouses: {len(missing)} referencias huérfanas" if missing else "  ✅ Inventory-Warehouses: OK")
    
    # Sales -> Products
    sales_prods = set(files["sales"]["product_id"])
    missing = sales_prods - prods
    print(f"  Sales-Products: {len(missing)} referencias huérfanas" if missing else "  ✅ Sales-Products: OK")
    
    print("\n📈 Estadísticas de datos:")
    for name, df in files.items():
        print(f"  {name}: {len(df)} registros, {len(df.columns)} columnas")
    
    print("\n✅ Verificación completada!")

if __name__ == "__main__":
    verify_data()