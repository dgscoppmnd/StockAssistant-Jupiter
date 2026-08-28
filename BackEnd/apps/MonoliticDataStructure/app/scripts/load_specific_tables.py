#!/usr/bin/env python
"""Script para cargar una tabla específica desde CSV a PostgreSQL"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging
from datetime import datetime
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración de base de datos
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "admin",
    "password": "admin123",
    "database": "supply_chain"
}

# Configuración de archivos
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"

# Definición de tablas disponibles
TABLES_CONFIG = {
    "products": {
        "file": DATA_DIR / "products.csv",
        "columns": ["product_id", "product_category", "brand", "sku", "product_cost_usd", "selling_price_usd"],
        "conflict": "ON CONFLICT (product_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    "suppliers": {
        "file": DATA_DIR / "suppliers.csv",
        "columns": ["supplier_id", "supplier_rating", "lead_time_days", "supplier_performance_score", "sustainability_score"],
        "conflict": "ON CONFLICT (supplier_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    "warehouses": {
        "file": DATA_DIR / "warehouses.csv",
        "columns": ["warehouse_id", "warehouse_location", "storage_capacity", "utilization_rate"],
        "conflict": "ON CONFLICT (warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    "inventory": {
        "file": DATA_DIR / "inventory.csv",
        "columns": ["product_id", "warehouse_id", "current_stock", "reorder_level", "safety_stock", 
                   "inventory_turnover", "stockout_risk", "overstock_risk", "inventory_optimization_score", 
                   "operational_risk_score"],
        "conflict": "ON CONFLICT (product_id, warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    "sales": {
        "file": DATA_DIR / "sales.csv",
        "columns": ["product_id", "date", "month", "quarter", "year", "units_sold", "daily_demand", 
                   "monthly_demand", "seasonal_demand_index", "revenue_usd", "profit_usd", 
                   "demand_forecast", "predicted_reorder_quantity"],
        "conflict": "ON CONFLICT (sales_id) DO NOTHING"
    },
    "logistics": {
        "file": DATA_DIR / "logistics.csv",
        "columns": ["product_id", "supplier_id", "warehouse_id", "shipping_cost_usd", "transportation_mode", 
                   "delivery_time_days", "on_time_delivery_rate", "supply_disruption_risk", 
                   "supply_chain_efficiency"],
        "conflict": "ON CONFLICT (product_id, supplier_id, warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    "supply_chain_metrics": {
        "file": DATA_DIR / "supply_chain_metrics.csv",
        "columns": ["product_id", "date", "inventory_optimization_score", "supplier_performance_score", 
                   "supply_chain_efficiency", "sustainability_score", "operational_risk_score"],
        "conflict": "ON CONFLICT (metric_id) DO NOTHING"
    }
}

def load_table(table_name, truncate_first=False, limit=None):
    """Carga una tabla específica desde CSV a PostgreSQL"""
    
    if table_name not in TABLES_CONFIG:
        logger.error(f"❌ Tabla '{table_name}' no encontrada. Opciones: {list(TABLES_CONFIG.keys())}")
        return
    
    table_config = TABLES_CONFIG[table_name]
    filepath = table_config["file"]
    columns = table_config["columns"]
    conflict = table_config["conflict"]
    
    if not filepath.exists():
        logger.error(f"❌ Archivo no encontrado: {filepath}")
        return
    
    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("✅ Conexión a PostgreSQL establecida")
        
        with conn.cursor() as cursor:
            # Opcional: truncar tabla
            if truncate_first:
                cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
                logger.info(f"🧹 Tabla {table_name} truncada")
            
            # Leer CSV
            if limit:
                df = pd.read_csv(filepath, nrows=limit)
                logger.info(f"📄 Leyendo {len(df)} registros de {filepath.name} (limitados a {limit})")
            else:
                df = pd.read_csv(filepath)
                logger.info(f"📄 Leyendo {len(df)} registros de {filepath.name}")
            
            if df.empty:
                logger.warning(f"⚠️ El archivo {filepath.name} está vacío")
                return
            
            # Validar columnas
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                logger.error(f"❌ Columnas faltantes: {missing_cols}")
                return
            
            # Añadir created_at si no existe
            if 'created_at' not in df.columns:
                df['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                columns_with_created = columns + ['created_at']
            else:
                columns_with_created = columns
            
            # Manejar valores nulos
            for col in df.columns:
                if df[col].dtype == 'float64':
                    df[col] = df[col].fillna(0)
                elif df[col].dtype == 'int64':
                    df[col] = df[col].fillna(0)
            
            # Convertir a lista de tuplas
            data = [tuple(row) for row in df[columns_with_created].values]
            
            # Construir query
            placeholders = ','.join(['%s'] * len(columns_with_created))
            column_names = ','.join(columns_with_created)
            query = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES %s
                {conflict}
            """
            
            # Ejecutar inserción
            execute_values(cursor, query, data, page_size=1000)
            conn.commit()
            
            logger.info(f"✅ Cargados {len(data)} registros en {table_name}")
            
            # Verificar conteo final
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            logger.info(f"📊 Total registros en {table_name}: {count:,}")
        
        conn.close()
        logger.info("🔌 Conexión cerrada")
        
    except Exception as e:
        logger.error(f"❌ Error cargando {table_name}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Cargar una tabla específica a PostgreSQL')
    parser.add_argument('table', choices=list(TABLES_CONFIG.keys()), 
                       help='Nombre de la tabla a cargar')
    parser.add_argument('--truncate', action='store_true', 
                       help='Truncar tabla antes de cargar')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limitar número de registros a cargar (para pruebas)')
    
    args = parser.parse_args()
    
    load_table(args.table, truncate_first=args.truncate, limit=args.limit)

if __name__ == "__main__":
    main()