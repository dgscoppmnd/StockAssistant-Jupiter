#!/usr/bin/env python
"""Script para cargar datos desde CSVs a PostgreSQL"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging
from pathlib import Path
from datetime import datetime
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# CONFIGURACIÓN
# =============================================

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "admin",
    "password": "admin123",
    "database": "supply_chain"
}

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "generated"

# Definir el orden de carga y sus archivos
LOAD_ORDER = [
    {
        "table": "products",
        "file": DATA_DIR / "products.csv",
        "columns": [
            "product_id", "product_category", "brand", "sku",
            "product_cost_usd", "selling_price_usd", "created_at"
        ],
        "conflict": "ON CONFLICT (product_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "suppliers",
        "file": DATA_DIR / "suppliers.csv",
        "columns": [
            "supplier_id", "supplier_rating", "lead_time_days",
            "supplier_performance_score", "sustainability_score", "created_at"
        ],
        "conflict": "ON CONFLICT (supplier_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "warehouses",
        "file": DATA_DIR / "warehouses.csv",
        "columns": [
            "warehouse_id", "warehouse_location", "storage_capacity",
            "utilization_rate", "created_at"
        ],
        "conflict": "ON CONFLICT (warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "inventory",
        "file": DATA_DIR / "inventory.csv",
        "columns": [
            "product_id", "warehouse_id", "current_stock", "reorder_level",
            "safety_stock", "inventory_turnover", "stockout_risk",
            "overstock_risk", "inventory_optimization_score",
            "operational_risk_score", "created_at"
        ],
        "conflict": "ON CONFLICT (product_id, warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "sales",
        "file": DATA_DIR / "sales.csv",
        "columns": [
            "product_id", "date", "month", "quarter", "year",
            "units_sold", "daily_demand", "monthly_demand",
            "seasonal_demand_index", "revenue_usd", "profit_usd",
            "demand_forecast", "predicted_reorder_quantity", "created_at"
        ],
        "conflict": "ON CONFLICT (sales_id) DO NOTHING"
    },
    {
        "table": "logistics",
        "file": DATA_DIR / "logistics.csv",
        "columns": [
            "product_id", "supplier_id", "warehouse_id",
            "shipping_cost_usd", "transportation_mode", "delivery_time_days",
            "on_time_delivery_rate", "supply_disruption_risk",
            "supply_chain_efficiency", "created_at"
        ],
        "conflict": "ON CONFLICT (product_id, supplier_id, warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "supply_chain_metrics",
        "file": DATA_DIR / "supply_chain_metrics.csv",
        "columns": [
            "product_id", "date", "inventory_optimization_score",
            "supplier_performance_score", "supply_chain_efficiency",
            "sustainability_score", "operational_risk_score", "created_at"
        ],
        "conflict": "ON CONFLICT (metric_id) DO NOTHING"
    }
]


# =============================================
# FUNCIONES PRINCIPALES
# =============================================

def connect_db():
    """Establece conexión con PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("✅ Conexión a PostgreSQL establecida")
        return conn
    except psycopg2.Error as e:
        logger.error(f"❌ Error conectando a PostgreSQL: {e}")
        sys.exit(1)

def load_csv_to_table(conn, table_info):
    """Carga un CSV a una tabla de PostgreSQL"""
    
    table = table_info["table"]
    filepath = table_info["file"]
    columns = table_info["columns"]
    conflict = table_info["conflict"]
    
    # Verificar que el archivo existe
    if not filepath.exists():
        logger.warning(f"⚠️ Archivo no encontrado: {filepath}")
        return 0
    
    try:
        # Leer CSV
        df = pd.read_csv(filepath)
        logger.info(f"📄 Leyendo {len(df)} registros de {filepath.name}")
        
        if df.empty:
            logger.warning(f"⚠️ El archivo {filepath.name} está vacío")
            return 0
        
        # Validar columnas
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            logger.error(f"❌ Columnas faltantes en {filepath.name}: {missing_cols}")
            return 0
        
        # Preparar datos para inserción
        # Manejar valores nulos
        df = df.fillna({
            'supplier_rating': 0,
            'lead_time_days': 0,
            'supplier_performance_score': 0,
            'sustainability_score': 0,
            'current_stock': 0,
            'reorder_level': 0,
            'safety_stock': 0,
            'inventory_turnover': 0,
            'stockout_risk': 0,
            'overstock_risk': 0,
            'inventory_optimization_score': 0,
            'operational_risk_score': 0,
            'shipping_cost_usd': 0,
            'delivery_time_days': 0,
            'on_time_delivery_rate': 0,
            'supply_disruption_risk': 0,
            'supply_chain_efficiency': 0,
            'units_sold': 0,
            'daily_demand': 0,
            'monthly_demand': 0,
            'seasonal_demand_index': 0,
            'revenue_usd': 0,
            'profit_usd': 0,
            'demand_forecast': 0,
            'predicted_reorder_quantity': 0
        })
        
        # Convertir a lista de tuplas
        data = [tuple(row) for row in df[columns].values]
        
        # Construir query
        placeholders = ','.join(['%s'] * len(columns))
        column_names = ','.join(columns)
        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES %s
            {conflict}
        """
        
        # Ejecutar inserción
        with conn.cursor() as cursor:
            execute_values(cursor, query, data)
            conn.commit()
            
        logger.info(f"✅ Cargados {len(data)} registros en {table}")
        return len(data)
        
    except Exception as e:
        logger.error(f"❌ Error cargando {table}: {e}")
        conn.rollback()
        return 0

def truncate_tables(conn, tables):
    """Elimina datos de todas las tablas en orden inverso"""
    
    # Invertir orden para respetar constraints
    reverse_tables = list(reversed([t["table"] for t in tables]))
    
    try:
        with conn.cursor() as cursor:
            for table in reverse_tables:
                cursor.execute(f"TRUNCATE TABLE {table} CASCADE;")
                logger.info(f"🧹 Tabla {table} truncada")
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Error truncando tablas: {e}")
        conn.rollback()

def verify_load(conn):
    """Verifica que los datos se cargaron correctamente"""
    
    with conn.cursor() as cursor:
        # Obtener conteo de todas las tablas
        cursor.execute("""
            SELECT 
                table_name,
                (SELECT COUNT(*) FROM information_schema.tables WHERE table_name = t.table_name)
            FROM information_schema.tables t
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        logger.info("\n📊 Resumen de carga:")
        for table_name, exists in tables:
            if exists:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                logger.info(f"  {table_name}: {count} registros")


# =============================================
# FUNCIÓN PRINCIPAL
# =============================================

def load_all_data(truncate_first=False):
    """Carga todos los datos en el orden correcto"""
    
    logger.info("="*60)
    logger.info("🚀 INICIANDO CARGA DE DATOS")
    logger.info("="*60)
    
    # Conectar a la base de datos
    conn = connect_db()
    
    try:
        # Opcional: truncar tablas
        if truncate_first:
            logger.info("\n🧹 Truncando tablas existentes...")
            truncate_tables(conn, LOAD_ORDER)
        
        # Cargar datos en orden
        total_records = 0
        for table_info in LOAD_ORDER:
            logger.info(f"\n📥 Cargando {table_info['table']}...")
            records = load_csv_to_table(conn, table_info)
            total_records += records
        
        # Verificar carga
        logger.info("\n" + "="*60)
        logger.info("✅ CARGA COMPLETADA")
        verify_load(conn)
        logger.info(f"\n📈 Total de registros cargados: {total_records}")
        
    except Exception as e:
        logger.error(f"❌ Error en el proceso de carga: {e}")
        conn.rollback()
    finally:
        conn.close()
        logger.info("🔌 Conexión cerrada")

def run():
    """Función principal para ejecutar desde script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Carga datos desde CSVs a PostgreSQL')
    parser.add_argument('--truncate', action='store_true', 
                       help='Truncar tablas antes de cargar')
    args = parser.parse_args()
    
    load_all_data(truncate_first=args.truncate)

if __name__ == "__main__":
    run()