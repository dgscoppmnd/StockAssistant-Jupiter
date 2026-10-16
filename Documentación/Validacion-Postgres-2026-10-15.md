# Comparación de init.sql y PostgreSQL en Docker

> Esta auditoría refleja el estado previo. Las diferencias se resolvieron posteriormente: [resultado de la migración](Resultado-Migracion-Postgres-2026-10-15.md).

Validación del 15 de octubre de 2026 sobre `proyecto_jupiter_db`, base `supply_chain`, PostgreSQL 15.14.
Captura del catálogo: 19:37:22 (Europe/Madrid; 17:37:22 UTC). Las consultas se ejecutaron con `transaction_read_only=on`.

## Resultado

No faltan tablas, columnas ni índices explícitos en `init.sql`. Sin embargo, el esquema real todavía no aplica todas las condiciones declaradas por el archivo.

| Elemento | init.sql | PostgreSQL | Resultado |
| --- | ---: | ---: | --- |
| Tablas | 66 | 66 | Coinciden |
| Columnas | 619 | 619 | Sin faltantes; tipos, identidades y columnas generadas coinciden |
| Restricciones PK/FK/UNIQUE/CHECK | 230 | 191 | Faltan 39 en PostgreSQL |
| Índices explícitos | 41 | 41 | Coinciden nombres y definiciones normalizadas |
| Vistas | 4 | 4 | Coinciden tras normalizar la representación de PostgreSQL |
| Funciones de aplicación | 5 | 5 | Coinciden cuerpos |
| Triggers | 8 | 8 | Coinciden definiciones |
| Columnas NOT NULL pendientes | — | 7 | Declaradas en el archivo, no exigidas en la base |
| Valores predeterminados pendientes | — | 33 | Declarados en el archivo, ausentes en la base |

La base contiene 137 índices en total: 41 explícitos y 96 asociados a claves primarias/restricciones únicas. No se comparan estos totales con 41 como si fueran índices faltantes.

## Restricciones ausentes en PostgreSQL

Hay 37 CHECK y 2 UNIQUE. Las claves primarias y foráneas declaradas coinciden.

### agent_action_proposals

- `CHECK ( action IN ( 'replenish' , 'transfer' , 'suspend_reorder' , 'promotion' , 'supplier_return' ) )`
- `CHECK ( status IN ( 'pending_approval' , 'approved' , 'executed' , 'rejected' , 'obsolete' ) )`

### inventory

- `CHECK ( current_stock >= 0 )`
- `CHECK ( inventory_optimization_score >= 0 AND inventory_optimization_score <= 100 )`
- `CHECK ( inventory_turnover >= 0 )`
- `CHECK ( operational_risk_score >= 0 AND operational_risk_score <= 100 )`
- `CHECK ( overstock_risk >= 0 AND overstock_risk <= 100 )`
- `CHECK ( reorder_level >= 0 )`
- `CHECK ( safety_stock >= 0 )`
- `CHECK ( stockout_risk >= 0 AND stockout_risk <= 100 )`
- `UNIQUE ( product_id , warehouse_id )`

### logistics

- `CHECK ( delivery_time_days >= 0 )`
- `CHECK ( on_time_delivery_rate >= 0 AND on_time_delivery_rate <= 100 )`
- `CHECK ( shipping_cost_usd >= 0 )`
- `CHECK ( supply_chain_efficiency >= 0 AND supply_chain_efficiency <= 100 )`
- `CHECK ( supply_disruption_risk >= 0 AND supply_disruption_risk <= 100 )`
- `UNIQUE ( product_id , supplier_id , warehouse_id )`

### products

- `CHECK ( product_cost_usd >= 0 )`
- `CHECK ( selling_price_usd >= 0 )`

### sales

- `CHECK ( daily_demand >= 0 )`
- `CHECK ( demand_forecast >= 0 )`
- `CHECK ( month BETWEEN 1 AND 12 )`
- `CHECK ( monthly_demand >= 0 )`
- `CHECK ( predicted_reorder_quantity >= 0 )`
- `CHECK ( quarter BETWEEN 1 AND 4 )`
- `CHECK ( revenue_usd >= 0 )`
- `CHECK ( units_sold >= 0 )`
- `CHECK ( year >= 2000 )`

### suppliers

- `CHECK ( lead_time_days >= 0 )`
- `CHECK ( supplier_performance_score >= 0 AND supplier_performance_score <= 100 )`
- `CHECK ( supplier_rating >= 0 AND supplier_rating <= 5 )`
- `CHECK ( sustainability_score >= 0 AND sustainability_score <= 100 )`

### supply_chain_metrics

- `CHECK ( inventory_optimization_score >= 0 AND inventory_optimization_score <= 100 )`
- `CHECK ( operational_risk_score >= 0 AND operational_risk_score <= 100 )`
- `CHECK ( supplier_performance_score >= 0 AND supplier_performance_score <= 100 )`
- `CHECK ( supply_chain_efficiency >= 0 AND supply_chain_efficiency <= 100 )`
- `CHECK ( sustainability_score >= 0 AND sustainability_score <= 100 )`

### warehouses

- `CHECK ( storage_capacity >= 0 )`
- `CHECK ( utilization_rate >= 0 AND utilization_rate <= 100 )`

## NOT NULL no aplicado

| Columna | init.sql | PostgreSQL |
| --- | --- | --- |
| `inventory.product_id` | NOT NULL | Permite NULL |
| `inventory.warehouse_id` | NOT NULL | Permite NULL |
| `sales.product_id` | NOT NULL | Permite NULL |
| `logistics.product_id` | NOT NULL | Permite NULL |
| `logistics.supplier_id` | NOT NULL | Permite NULL |
| `logistics.warehouse_id` | NOT NULL | Permite NULL |
| `supply_chain_metrics.product_id` | NOT NULL | Permite NULL |

## Defaults ausentes

| Columna | Default en init.sql | PostgreSQL |
| --- | --- | --- |
| `products.created_at` | `CURRENT_TIMESTAMP` | Sin default |
| `products.updated_at` | `CURRENT_TIMESTAMP` | Sin default |
| `suppliers.created_at` | `CURRENT_TIMESTAMP` | Sin default |
| `suppliers.updated_at` | `CURRENT_TIMESTAMP` | Sin default |
| `warehouses.created_at` | `CURRENT_TIMESTAMP` | Sin default |
| `warehouses.updated_at` | `CURRENT_TIMESTAMP` | Sin default |
| `inventory.current_stock` | `0` | Sin default |
| `inventory.reorder_level` | `0` | Sin default |
| `inventory.safety_stock` | `0` | Sin default |
| `inventory.inventory_turnover` | `0` | Sin default |
| `inventory.stockout_risk` | `0` | Sin default |
| `inventory.overstock_risk` | `0` | Sin default |
| `inventory.inventory_optimization_score` | `0` | Sin default |
| `inventory.operational_risk_score` | `0` | Sin default |
| `inventory.created_at` | `CURRENT_TIMESTAMP` | Sin default |
| `inventory.updated_at` | `CURRENT_TIMESTAMP` | Sin default |
| `sales.units_sold` | `0` | Sin default |
| `sales.daily_demand` | `0` | Sin default |
| `sales.monthly_demand` | `0` | Sin default |
| `sales.seasonal_demand_index` | `0` | Sin default |
| `sales.revenue_usd` | `0` | Sin default |
| `sales.profit_usd` | `0` | Sin default |
| `sales.demand_forecast` | `0` | Sin default |
| `sales.predicted_reorder_quantity` | `0` | Sin default |
| `sales.created_at` | `CURRENT_TIMESTAMP` | Sin default |
| `logistics.shipping_cost_usd` | `0` | Sin default |
| `logistics.delivery_time_days` | `0` | Sin default |
| `logistics.on_time_delivery_rate` | `0` | Sin default |
| `logistics.supply_disruption_risk` | `0` | Sin default |
| `logistics.supply_chain_efficiency` | `0` | Sin default |
| `logistics.created_at` | `CURRENT_TIMESTAMP` | Sin default |
| `logistics.updated_at` | `CURRENT_TIMESTAMP` | Sin default |
| `supply_chain_metrics.created_at` | `CURRENT_TIMESTAMP` | Sin default |

## Comprobación previa de datos

Se hicieron 46 comprobaciones agregadas: 37 expresiones CHECK, 2 grupos UNIQUE y 7 columnas NOT NULL. Todas devolvieron cero incidencias. No se extrajeron filas de negocio.

Este resultado es una instantánea. No se han agregado restricciones ni defaults, ni se ha ejecutado init.sql. No se ha creado ni eliminado ninguna base de datos.

## Qué falta antes de sincronizar

El archivo declara estas condiciones dentro de CREATE TABLE IF NOT EXISTS. Esa cláusula conserva las tablas existentes y no agrega a esas tablas las restricciones, defaults o NOT NULL pendientes. Para que también actualice instalaciones existentes faltan migraciones ALTER TABLE explícitas para esas diferencias, con comprobaciones idempotentes y validación de datos.

No conviene eliminar del SQL las condiciones de integridad para imitar una base más permisiva. No se ha preparado ni aplicado ese cambio; primero debe revisarse este informe.

## Alcance y evidencias

Comparación estática de declaraciones SQL frente a catálogos públicos, con normalización de alias de tipos, casts y expresiones equivalentes IN/ANY y BETWEEN. No se compararon permisos, propietarios, parámetros físicos de secuencias, versiones requeridas de extensiones ni contenido/semillas de negocio. No sustituye una migración probada en un entorno de ensayo.

- [Catálogo capturado](Postgres-Schema-Audit-2026-10-15.json)
- [Diferencias detalladas](Postgres-Schema-Differences-2026-10-15.json)
- [Recuentos previos de datos](Postgres-Schema-Prechecks-2026-10-15.json)

Hash SHA-256 del contenido normalizado de init.sql: `8f74dbded90a67153fcd021b3944c26d44e00de8cf534dfedbdd21ae40bcf22f`. Se comprobó que el archivo no cambió durante la auditoría.
