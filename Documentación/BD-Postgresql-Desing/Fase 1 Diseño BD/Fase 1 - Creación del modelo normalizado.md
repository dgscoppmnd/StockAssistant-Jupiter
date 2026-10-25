#  Fase 1: Diseño de la Base de Datos Normalizada

##  Análisis y Normalización

**Tabla original (Kaggle_Dataset)** - No normalizada:
- Contiene datos de: Productos, Proveedores, Almacenes, Ventas, Logística, Métricas

Vamos a descomponer en **7 tablas**:

---

##  Tablas Diseñadas

### 1. PRODUCTOS
```sql
CREATE TABLE products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_category VARCHAR(50),
    brand VARCHAR(50),
    sku VARCHAR(50) UNIQUE,
    product_cost_usd DECIMAL(10,2),
    selling_price_usd DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. PROVEEDORES
```sql
CREATE TABLE suppliers (
    supplier_id VARCHAR(20) PRIMARY KEY,
    supplier_rating DECIMAL(3,2),
    lead_time_days INTEGER,
    supplier_performance_score DECIMAL(5,2),
    sustainability_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. ALMACENES
```sql
CREATE TABLE warehouses (
    warehouse_id VARCHAR(20) PRIMARY KEY,
    warehouse_location VARCHAR(50),
    storage_capacity INTEGER,
    utilization_rate DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. INVENTARIO (relación producto-almacén)
```sql
CREATE TABLE inventory (
    inventory_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) REFERENCES products(product_id),
    warehouse_id VARCHAR(20) REFERENCES warehouses(warehouse_id),
    current_stock INTEGER,
    reorder_level INTEGER,
    safety_stock INTEGER,
    inventory_turnover DECIMAL(10,2),
    stockout_risk DECIMAL(5,2),
    overstock_risk DECIMAL(5,2),
    inventory_optimization_score DECIMAL(5,2),
    operational_risk_score DECIMAL(5,2),
    UNIQUE(product_id, warehouse_id)
);
```

### 5. VENTAS (mensual)
```sql
CREATE TABLE sales (
    sales_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) REFERENCES products(product_id),
    date DATE,
    month INTEGER,
    quarter INTEGER,
    year INTEGER,
    units_sold INTEGER,
    daily_demand INTEGER,
    monthly_demand INTEGER,
    seasonal_demand_index DECIMAL(5,2),
    revenue_usd DECIMAL(12,2),
    profit_usd DECIMAL(12,2),
    demand_forecast INTEGER,
    predicted_reorder_quantity INTEGER
);
```

### 6. LOGÍSTICA
```sql
CREATE TABLE logistics (
    logistics_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) REFERENCES products(product_id),
    supplier_id VARCHAR(20) REFERENCES suppliers(supplier_id),
    warehouse_id VARCHAR(20) REFERENCES warehouses(warehouse_id),
    shipping_cost_usd DECIMAL(10,2),
    transportation_mode VARCHAR(20),
    delivery_time_days INTEGER,
    on_time_delivery_rate DECIMAL(5,2),
    supply_disruption_risk DECIMAL(5,2),
    supply_chain_efficiency DECIMAL(5,2)
);
```

### 7. MÉTRICAS AGREGADAS (para análisis rápido)
```sql
CREATE TABLE supply_chain_metrics (
    metric_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) REFERENCES products(product_id),
    date DATE,
    inventory_optimization_score DECIMAL(5,2),
    supplier_performance_score DECIMAL(5,2),
    supply_chain_efficiency DECIMAL(5,2),
    sustainability_score DECIMAL(5,2),
    operational_risk_score DECIMAL(5,2)
);
```

---

##  Diagrama ER

```text
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  PRODUCTS   │◄────────│  INVENTORY   │────────►│ WAREHOUSES  │
│             │         │              │         │             │
│ product_id  │         │ product_id   │         │ warehouse_id│
│ category    │         │ warehouse_id │         │ location    │
│ brand       │         │ current_stock│         │ capacity    │
│ sku         │         │ reorder_level│         └─────────────┘
│ cost        │         └──────────────┘
│ price       │              │
└─────────────┘              │
      │                       │
      │                       │
      ▼                       ▼
┌─────────────┐         ┌──────────────┐
│    SALES    │         │  LOGISTICS   │
│             │         │              │
│ product_id  │         │ product_id   │
│ date        │         │ supplier_id  │
│ units_sold  │         │ warehouse_id │
│ revenue     │         │ shipping_cost│
│ profit      │         │ transport_mode│
└─────────────┘         └──────────────┘
      │                       │
      │                       │
      └───────────┬───────────┘
                  ▼
┌─────────────────────────────────┐
│      SUPPLIERS                  │
│                                 │
│ supplier_id PRIMARY KEY         │
│ rating                          │
│ lead_time_days                  │
└─────────────────────────────────┘
```

---

##  Relaciones Clave

| Tabla Origen | Tabla Destino | Tipo de Relación |
|--------------|---------------|------------------|
| `inventory`  | `products`    | N:1 (Muchos inventarios por producto) |
| `inventory`  | `warehouses`  | N:1 (Muchos inventarios por almacén) |
| `sales`      | `products`    | N:1 (Muchas ventas por producto) |
| `logistics`  | `products`    | N:1 (Muchos registros logísticos por producto) |
| `logistics`  | `suppliers`   | N:1 (Muchos registros por proveedor) |
| `logistics`  | `warehouses`  | N:1 (Muchos registros por almacén) |
| `supply_chain_metrics` | `products` | N:1 (Muchas métricas por producto) |

---

##  Notas de Diseño

- **3FN (Tercera Forma Normal)** aplicada: todas las tablas tienen clave primaria y las dependencias transitivas han sido eliminadas
- **Integridad referencial** asegurada mediante claves foráneas (`REFERENCES`)
- **Restricciones UNIQUE** en `sku` y en el par `(product_id, warehouse_id)` para evitar duplicados
- **Campos calculados** en `supply_chain_metrics` para acelerar consultas analíticas
- **Tipos de datos** optimizados: `VARCHAR` para texto corto, `TEXT` para descripciones largas, `DECIMAL` para valores monetarios y porcentajes

---

##  Próximo Paso

[[Fase 2- Infraestructura con Docker]]

---

##  Etiquetas
#database-design #postgresql #normalization #supply-chain #fase1