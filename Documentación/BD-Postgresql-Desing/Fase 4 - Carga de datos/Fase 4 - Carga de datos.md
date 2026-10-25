#  Carga de Datos en PostgreSQL

##  Descripción General

Este documento documenta el proceso de carga de datos desde los archivos CSV generados en la fase anterior hacia la base de datos PostgreSQL, incluyendo la configuración de infraestructura, scripts de carga y resolución de problemas.

---

##  Estructura del Proyecto

```text
data/
└── generated/
    ├── products.csv                 # Productos (200K registros)
    ├── suppliers.csv               # Proveedores (4,999 registros)
    ├── warehouses.csv              # Almacenes (20 registros)
    ├── inventory.csv               # Inventario (399K registros)
    ├── sales.csv                   # Ventas (899K registros)
    ├── logistics.csv               # Logística (200K registros)
    └── supply_chain_metrics.csv    # Métricas (1.1M registros)

src/
└── database/
    ├── __init__.py
    ├── connection.py               # Configuración de conexión
    └── loader.py                   # Script principal de carga

scripts/
├── load_data.py                    # Ejecutor de carga
└── load_specific_table.py          # Carga selectiva por tabla
```

---

##  Configuración de Infraestructura

### Docker Compose con Memoria Compartida

```yaml
# docker/docker-compose.yml
services:
  postgres:
    image: postgres:15-alpine
    container_name: supply_chain_db
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin123
      POSTGRES_DB: supply_chain
    ports:
      - "5432:5432"
    shm_size: 1gb  # Memoria compartida para grandes cargas
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
      - ./postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    command: >
      postgres 
      -c listen_addresses='*'
      -c max_connections=100
      -c shared_buffers=512MB
      -c work_mem=64MB
      -c maintenance_work_mem=256MB
      -c max_parallel_workers=4
```

### Configuración de PostgreSQL

```conf
# docker/postgres/postgresql.conf
shared_buffers = 512MB
work_mem = 64MB
maintenance_work_mem = 256MB
effective_cache_size = 2GB
max_parallel_workers = 4
max_parallel_workers_per_gather = 2
```

---

##  Orden de Carga

Las tablas deben cargarse en este orden para respetar las claves foráneas:

| Orden | Tabla | Dependencias | Registros Estimados |
|-------|-------|--------------|---------------------|
| 1 | `products` | Ninguna | 200,000 |
| 2 | `suppliers` | Ninguna | 4,999 |
| 3 | `warehouses` | Ninguna | 20 |
| 4 | `inventory` | `products`, `warehouses` | 399,729 |
| 5 | `sales` | `products` | 899,004 |
| 6 | `logistics` | `products`, `suppliers`, `warehouses` | 200,000 |
| 7 | `supply_chain_metrics` | `products` | 1,098,507 |

---

##  Script de Carga Principal

**src/database/loader.py**:

```python
#!/usr/bin/env python
"""Script para cargar datos desde CSVs a PostgreSQL - VERSIÓN CON LOTES"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging
from pathlib import Path
from datetime import datetime
import sys
import uuid

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
BATCH_SIZE = 10000  # Tamaño de lote para evitar problemas de memoria

# Definición de tablas
LOAD_ORDER = [
    {
        "table": "products",
        "file": DATA_DIR / "products.csv",
        "columns": [
            "product_id", "product_category", "brand", "sku",
            "product_cost_usd", "selling_price_usd"
        ],
        "conflict": "ON CONFLICT (product_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "suppliers",
        "file": DATA_DIR / "suppliers.csv",
        "columns": [
            "supplier_id", "supplier_rating", "lead_time_days",
            "supplier_performance_score", "sustainability_score"
        ],
        "conflict": "ON CONFLICT (supplier_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "warehouses",
        "file": DATA_DIR / "warehouses.csv",
        "columns": [
            "warehouse_id", "warehouse_location", "storage_capacity",
            "utilization_rate"
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
            "operational_risk_score"
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
            "demand_forecast", "predicted_reorder_quantity"
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
            "supply_chain_efficiency"
        ],
        "conflict": "ON CONFLICT (product_id, supplier_id, warehouse_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
    },
    {
        "table": "supply_chain_metrics",
        "file": DATA_DIR / "supply_chain_metrics.csv",
        "columns": [
            "product_id", "date", "inventory_optimization_score",
            "supplier_performance_score", "supply_chain_efficiency",
            "sustainability_score", "operational_risk_score"
        ],
        "conflict": "ON CONFLICT (metric_id) DO NOTHING"
    }
]

def load_csv_to_table(conn, table_info):
    """Carga un CSV a una tabla de PostgreSQL en lotes"""
    
    table = table_info["table"]
    filepath = table_info["file"]
    columns = table_info["columns"]
    conflict = table_info["conflict"]
    
    if not filepath.exists():
        logger.warning(f"⚠️ Archivo no encontrado: {filepath}")
        return 0
    
    try:
        total_loaded = 0
        chunk_size = BATCH_SIZE
        
        logger.info(f"📄 Cargando {filepath.name} en lotes de {chunk_size}...")
        
        for chunk_idx, df_chunk in enumerate(pd.read_csv(filepath, chunksize=chunk_size)):
            logger.info(f"  Procesando lote {chunk_idx + 1} ({len(df_chunk)} registros)...")
            
            # Añadir created_at
            df_chunk['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cols_to_use = columns + ['created_at']
            
            # Manejar valores nulos
            for col in df_chunk.columns:
                if df_chunk[col].dtype == 'float64':
                    df_chunk[col] = df_chunk[col].fillna(0)
                elif df_chunk[col].dtype == 'int64':
                    df_chunk[col] = df_chunk[col].fillna(0)
            
            # Convertir a tuplas
            data = [tuple(row) for row in df_chunk[cols_to_use].values]
            
            # Query de inserción
            placeholders = ','.join(['%s'] * len(cols_to_use))
            column_names = ','.join(cols_to_use)
            query = f"""
                INSERT INTO {table} ({column_names})
                VALUES %s
                {conflict}
            """
            
            # Ejecutar
            with conn.cursor() as cursor:
                execute_values(cursor, query, data, page_size=1000)
                conn.commit()
            
            total_loaded += len(data)
            logger.info(f"    ✅ Lote {chunk_idx + 1} cargado: {len(data)} registros")
        
        logger.info(f"✅ Cargados {total_loaded} registros en {table}")
        return total_loaded
        
    except Exception as e:
        logger.error(f"❌ Error cargando {table}: {e}")
        conn.rollback()
        return 0
```

---

##  Comandos de Ejecución

### Carga Completa
```bash
# Cargar todos los datos (con truncado)
python scripts/load_data.py --truncate

# Cargar todos los datos (sin truncar)
python scripts/load_data.py
```

### Carga Selectiva por Tabla
```bash
# Cargar solo una tabla específica
python scripts/load_specific_table.py supply_chain_metrics --truncate

# Opciones disponibles:
# --truncate : Borrar datos existentes antes de cargar
# --limit N  : Limitar número de registros (para pruebas)
```

### Carga Rápida para Metrics
```bash
# Script optimizado solo para metrics
python scripts/load_metrics_quick.py
```

---

##  Verificación de Carga

### Consultas SQL de Validación

```sql
-- Verificar conteo de todas las tablas
SELECT 
    'products' as tabla, COUNT(*) as registros FROM products
UNION ALL
SELECT 'suppliers', COUNT(*) FROM suppliers
UNION ALL
SELECT 'warehouses', COUNT(*) FROM warehouses
UNION ALL
SELECT 'inventory', COUNT(*) FROM inventory
UNION ALL
SELECT 'sales', COUNT(*) FROM sales
UNION ALL
SELECT 'logistics', COUNT(*) FROM logistics
UNION ALL
SELECT 'supply_chain_metrics', COUNT(*) FROM supply_chain_metrics
ORDER BY tabla;

-- Verificar integridad referencial (sin huérfanos)
SELECT 
    'inventory' as tabla, 
    COUNT(*) as huérfanos 
FROM inventory i
LEFT JOIN products p ON i.product_id = p.product_id
WHERE p.product_id IS NULL;

-- Verificar SKUs duplicados (no debería haber)
SELECT sku, COUNT(*) 
FROM products 
GROUP BY sku 
HAVING COUNT(*) > 1;
```

### Script de Verificación Automática

**scripts/verify_load.py**:

```python
import psycopg2
import pandas as pd

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "admin",
    "password": "admin123",
    "database": "supply_chain"
}

def verify_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    
    tables = ['products', 'suppliers', 'warehouses', 'inventory', 
              'sales', 'logistics', 'supply_chain_metrics']
    
    print("📊 Resumen de carga:")
    total_records = 0
    
    for table in tables:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        total_records += count
        status = "✅" if count > 0 else "⚠️"
        print(f"  {status} {table}: {count:,} registros")
    
    print(f"\n📈 Total: {total_records:,} registros")
    conn.close()

if __name__ == "__main__":
    verify_tables()
```

---

##  Resolución de Problemas

### Error: "could not resize shared memory segment"

**Causa**: Memoria compartida insuficiente para grandes cargas.

**Solución**:

1. Aumentar `shm_size` en `docker-compose.yml`:
   ```yaml
   services:
     postgres:
       shm_size: 1gb
   ```

2. Aumentar recursos en Docker Desktop:
   - Settings → Resources → Memory: 4GB+
   - Swap: 1GB+

3. Reducir `BATCH_SIZE` en el script:
   ```python
   BATCH_SIZE = 5000  # En lugar de 10000
   ```

### Error: "duplicate key value violates unique constraint"

**Causa**: SKUs duplicados en la tabla products.

**Solución**: El script de carga regenera SKUs duplicados automáticamente.

### Error: "column created_at does not exist"

**Causa**: El CSV no tiene la columna created_at.

**Solución**: El script añade created_at automáticamente durante la carga.

### Error de Conexión

**Solución**:
```bash
# Verificar que PostgreSQL está corriendo
docker ps | grep supply_chain_db

# Ver logs del contenedor
docker logs supply_chain_db --tail 20

# Verificar conexión
docker exec -it supply_chain_db psql -U admin -d supply_chain -c "SELECT 1;"
```

---

##  Estadísticas de Carga

| Tabla | Registros | Tiempo Estimado |
|-------|-----------|-----------------|
| `products` | 200,000 | ~30 segundos |
| `suppliers` | 4,999 | ~2 segundos |
| `warehouses` | 20 | <1 segundo |
| `inventory` | 399,729 | ~2 minutos |
| `sales` | 899,004 | ~5 minutos |
| `logistics` | 200,000 | ~1 minuto |
| `supply_chain_metrics` | 1,098,507 | ~8 minutos |
| **Total** | **~2.8M** | **~17 minutos** |

---

##  Checklist de Carga

- [ ] PostgreSQL corriendo (`docker-compose ps`)
- [ ] Archivos CSV generados en `data/generated/`
- [ ] Conexión a BD verificada
- [ ] Orden de carga respetado
- [ ] Todas las tablas cargadas sin errores
- [ ] Verificación de integridad referencial
- [ ] Consultas de validación ejecutadas
- [ ] Registros de carga documentados

---

##  Recursos Relacionados

- [[Fase 1: Diseño de BD]]
- [[Fase 2: Generación de Datos]]
- [[Fase 2: Infraestructura Docker]]
- [[Fase 5: API con FastAPI]]

---

##  Estado Actual

- **Estado**: ✅ Carga completada con éxito
- **Fecha**: 2026-08-13
- **Siguiente Paso**: [[Fase 5: API con FastAPI]]

---

##  Etiquetas

#postgresql #data-loading #etl #supply-chain #database #tfm