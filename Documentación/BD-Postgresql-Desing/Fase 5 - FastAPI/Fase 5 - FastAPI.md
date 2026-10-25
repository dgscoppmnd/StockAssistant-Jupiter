#  API con FastAPI - Supply Chain Management

##  Descripción General

API RESTful desarrollada con FastAPI para exponer los datos de la cadena de suministro, permitiendo consultas para el sistema de IA de gestión de stock y facilitando el acceso a los datos para análisis posteriores.

---

##  Arquitectura de la API

```text
src/api/
├── main.py                      # Aplicación principal
├── config.py                    # Configuración
├── database.py                  # Conexión a PostgreSQL
├── models.py                    # Modelos SQLAlchemy
├── schemas.py                   # Schemas Pydantic
├── dependencies.py              # Dependencias comunes
├── routes/                      # Endpoints
│   ├── products.py              # Productos
│   ├── inventory.py             # Inventario
│   ├── sales.py                 # Ventas
│   ├── suppliers.py             # Proveedores
│   ├── logistics.py             # Logística
│   ├── metrics.py               # Métricas
│   └── analytics.py             # Análisis
└── utils/
    └── pagination.py            # Paginación
```

---

##  Dependencias

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.22
psycopg2-binary==2.9.9
pydantic==2.4.2
pydantic-settings==2.0.3
python-dotenv==1.0.0
```

---

##  Configuración

### Variables de Entorno (.env)

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=admin123
DB_NAME=supply_chain
API_TITLE=Supply Chain Management API
API_VERSION=1.0.0
```

### Configuración (config.py)

```python
class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "admin"
    DB_PASSWORD: str = "admin123"
    DB_NAME: str = "supply_chain"
    API_TITLE: str = "Supply Chain Management API"
    API_VERSION: str = "1.0.0"
    ALLOWED_ORIGINS: list = ["*"]
    
    class Config:
        extra = "ignore"  # Ignorar campos no definidos
```

---

##  Modelos de Base de Datos

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| `Product` | `products` | Catálogo de productos |
| `Supplier` | `suppliers` | Proveedores |
| `Warehouse` | `warehouses` | Almacenes |
| `Inventory` | `inventory` | Stock y métricas |
| `Sales` | `sales` | Ventas históricas |
| `Logistics` | `logistics` | Datos logísticos |
| `SupplyChainMetric` | `supply_chain_metrics` | Métricas de rendimiento |

---

##  Endpoints Disponibles

### Productos (`/api/v1/products`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Listar productos con filtros |
| `GET` | `/{product_id}` | Obtener producto por ID |
| `GET` | `/search/{sku}` | Buscar por SKU |
| `GET` | `/categories/` | Listar categorías |
| `GET` | `/brands/` | Listar marcas |
| `POST` | `/` | Crear nuevo producto |

**Parámetros de filtro:**
- `category`: Categoría del producto
- `brand`: Marca del producto
- `search`: Búsqueda en ID, SKU o marca
- `skip`: Paginación - saltar N registros
- `limit`: Paginación - límite de registros

### Inventario (`/api/v1/inventory`)

| Método | Endpoint                  | Descripción                   |
| ------ | ------------------------- | ----------------------------- |
| `GET`  | `/`                       | Listar inventario con filtros |
| `GET`  | `/critical`               | Productos con stock crítico   |
| `GET`  | `/overstock`              | Productos con exceso de stock |
| `GET`  | `/warehouse/{id}/summary` | Resumen por almacén           |
| `GET`  | `/product/{id}`           | Inventario de un producto     |

**Parámetros de filtro:**
- `warehouse_id`: Filtrar por almacén
- `product_id`: Filtrar por producto
- `min_stock`: Stock mínimo
- `max_stock`: Stock máximo
- `critical_only`: Solo stock crítico

### Ventas (`/api/v1/sales`)

| Método | Endpoint        | Descripción               |
| ------ | --------------- | ------------------------- |
| `GET`  | `/`             | Listar ventas con filtros |
| `GET`  | `/trends`       | Tendencias de ventas      |
| `GET`  | `/summary`      | Resumen de ventas         |
| `GET`  | `/top-products` | Productos más vendidos    |

### Proveedores (`/api/v1/suppliers`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Listar proveedores |
| `GET` | `/{id}` | Obtener proveedor |
| `GET` | `/efficiency` | Eficiencia de proveedores |
| `GET` | `/{id}/performance` | Rendimiento detallado |

### Logística (`/api/v1/logistics`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Listar registros logísticos |
| `GET` | `/transport-modes` | Modos de transporte |
| `GET` | `/summary` | Resumen logístico |
| `GET` | `/efficiency` | Métricas de eficiencia |

### Métricas (`/api/v1/metrics`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Listar métricas |
| `GET` | `/product/{id}` | Métricas de un producto |
| `GET` | `/summary` | Resumen por categoría |

### Análisis (`/api/v1/analytics`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/product-performance` | Rendimiento de productos |
| `GET` | `/risk-analysis` | Análisis de riesgos |
| `GET` | `/inventory-optimization` | Optimización de inventario |

---

##  Ejemplos de Uso

### Obtener productos con filtros

```bash
# Productos de la categoría Electronics
curl "http://localhost:8000/api/v1/products?category=Electronics&limit=10"

# Buscar productos por marca
curl "http://localhost:8000/api/v1/products?brand=BrandA"

# Búsqueda general
curl "http://localhost:8000/api/v1/products?search=PRD0001"
```

### Obtener stock crítico

```bash
# Todos los productos con stock crítico
curl "http://localhost:8000/api/v1/inventory/critical"

# Stock crítico en un almacén específico
curl "http://localhost:8000/api/v1/inventory/critical?warehouse_id=WH001"
```

### Análisis de rendimiento

```bash
# Top 10 productos por rendimiento
curl "http://localhost:8000/api/v1/analytics/product-performance?limit=10"

# Filtrado por categoría
curl "http://localhost:8000/api/v1/analytics/product-performance?category=Electronics"
```

### Tendencias de ventas

```bash
# Últimos 30 días
curl "http://localhost:8000/api/v1/sales/trends?days=30"

# Para un producto específico
curl "http://localhost:8000/api/v1/sales/trends?product_id=PRD0000001&days=90"
```

---

##  Comandos de Ejecución

### Iniciar la API

```bash
# Usando el script
python scripts/run_api.py

# O usando uvicorn directamente
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Probar la configuración

```bash
python scripts/test_config.py
```

---

##  Respuestas de la API

### Paginación

Todas las respuestas de listado incluyen paginación:

```json
{
    "items": [...],
    "total": 200000,
    "skip": 0,
    "limit": 100,
    "has_more": true
}
```

### Formato de Fechas

Las fechas se devuelven en formato ISO-8601:
- `"2026-08-13T19:08:07.130"` (DateTime)
- `"2026-08-13"` (Date)

### Códigos de Estado

| Código | Significado |
|--------|-------------|
| 200 | OK |
| 404 | No encontrado |
| 422 | Error de validación |
| 500 | Error interno |

---

##  Resolución de Problemas

### Error: ImportError: cannot import name 'suppliers'

**Causa**: Falta el archivo `suppliers.py` o importación circular.

**Solución**: Crear el archivo faltante y verificar `__init__.py`.

### Error: AttributeError: 'Settings' object has no attribute 'DATABASE_URL'

**Causa**: `DATABASE_URL` definido fuera de la clase.

**Solución**: Usar `settings.DATABASE_URL` o definir como propiedad.

### Error: pydantic_core._pydantic_core.ValidationError

**Causa**: Campos extra en el `.env` no definidos en `Settings`.

**Solución**: Añadir `extra = "ignore"` en la clase `Config`.

---

##  Estadísticas de la API

| Métrica | Valor |
|---------|-------|
| Endpoints | 35+ |
| Modelos | 7 tablas |
| Schemas | 15+ |
| Tiempo de respuesta | < 100ms (caché) |
| Carga máxima | 2.8M registros |

---

##  Recursos Relacionados

- [[Fase 1: Diseño de BD]]
- [[Fase 2: Generación de Datos]]
- [[Fase 2: Infraestructura Docker]]
- [[Fase 4: Carga de Datos]]
- [Documentación FastAPI](https://fastapi.tiangolo.com/)

---

## Checklist de Implementación

- [x] Estructura de directorios creada
- [x] Dependencias instaladas
- [x] Configuración de base de datos
- [x] Modelos SQLAlchemy definidos
- [x] Schemas Pydantic creados
- [x] Endpoints implementados (7 módulos)
- [x] Paginación implementada
- [x] Conexión a BD verificada
- [x] API funcionando en http://localhost:8000
- [x] Documentación accesible en /docs
- [x] Redoc accesible en /redoc
- [x] Pruebas de endpoints realizadas

---

##  Estado Actual

- **Estado**: API implementada y funcionando
- **Fecha**: 2026-08-13
- **URL**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Siguiente Paso**: Integración con sistema de IA

---

##  Etiquetas

#fastapi #api #rest #supply-chain #python #postgresql #tfm