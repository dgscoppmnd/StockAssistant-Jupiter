-- Conectar a la base de datos

-- Habilitar extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================
-- 1. TABLA: PRODUCTS
-- =============================================
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_category VARCHAR(50) NOT NULL,
    brand VARCHAR(50),
    sku VARCHAR(50) UNIQUE NOT NULL,
    product_cost_usd DECIMAL(12,2) CHECK (product_cost_usd >= 0),
    selling_price_usd DECIMAL(12,2) CHECK (selling_price_usd >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_products_category ON products(product_category);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);

-- =============================================
-- 2. TABLA: SUPPLIERS
-- =============================================
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id VARCHAR(20) PRIMARY KEY,
    supplier_rating DECIMAL(3,2) CHECK (supplier_rating >= 0 AND supplier_rating <= 5),
    lead_time_days INTEGER CHECK (lead_time_days >= 0),
    supplier_performance_score DECIMAL(5,2) CHECK (supplier_performance_score >= 0 AND supplier_performance_score <= 100),
    sustainability_score DECIMAL(5,2) CHECK (sustainability_score >= 0 AND sustainability_score <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 3. TABLA: WAREHOUSES
-- =============================================
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id VARCHAR(20) PRIMARY KEY,
    warehouse_location VARCHAR(50) NOT NULL,
    storage_capacity INTEGER CHECK (storage_capacity >= 0),
    utilization_rate DECIMAL(5,2) CHECK (utilization_rate >= 0 AND utilization_rate <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_warehouses_location ON warehouses(warehouse_location);

-- =============================================
-- 4. TABLA: INVENTORY
-- =============================================
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    current_stock INTEGER DEFAULT 0 CHECK (current_stock >= 0),
    reorder_level INTEGER DEFAULT 0 CHECK (reorder_level >= 0),
    safety_stock INTEGER DEFAULT 0 CHECK (safety_stock >= 0),
    inventory_turnover DECIMAL(10,2) DEFAULT 0 CHECK (inventory_turnover >= 0),
    stockout_risk DECIMAL(5,2) DEFAULT 0 CHECK (stockout_risk >= 0 AND stockout_risk <= 100),
    overstock_risk DECIMAL(5,2) DEFAULT 0 CHECK (overstock_risk >= 0 AND overstock_risk <= 100),
    inventory_optimization_score DECIMAL(5,2) DEFAULT 0 CHECK (inventory_optimization_score >= 0 AND inventory_optimization_score <= 100),
    operational_risk_score DECIMAL(5,2) DEFAULT 0 CHECK (operational_risk_score >= 0 AND operational_risk_score <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, warehouse_id)
);

-- Índices para consultas de inventario
CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_inventory_stock ON inventory(current_stock);

-- =============================================
-- 5. TABLA: SALES
-- =============================================
CREATE TABLE IF NOT EXISTS sales (
    sales_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    month INTEGER CHECK (month BETWEEN 1 AND 12),
    quarter INTEGER CHECK (quarter BETWEEN 1 AND 4),
    year INTEGER CHECK (year >= 2000),
    units_sold INTEGER DEFAULT 0 CHECK (units_sold >= 0),
    daily_demand INTEGER DEFAULT 0 CHECK (daily_demand >= 0),
    monthly_demand INTEGER DEFAULT 0 CHECK (monthly_demand >= 0),
    seasonal_demand_index DECIMAL(5,2) DEFAULT 0,
    revenue_usd DECIMAL(15,2) DEFAULT 0 CHECK (revenue_usd >= 0),
    profit_usd DECIMAL(15,2) DEFAULT 0,
    demand_forecast INTEGER DEFAULT 0 CHECK (demand_forecast >= 0),
    predicted_reorder_quantity INTEGER DEFAULT 0 CHECK (predicted_reorder_quantity >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para análisis de ventas
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
CREATE INDEX IF NOT EXISTS idx_sales_year_month ON sales(year, month);
CREATE INDEX IF NOT EXISTS idx_sales_quarter ON sales(year, quarter);

-- =============================================
-- 6. TABLA: LOGISTICS
-- =============================================
CREATE TABLE IF NOT EXISTS logistics (
    logistics_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    supplier_id VARCHAR(20) NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    shipping_cost_usd DECIMAL(12,2) DEFAULT 0 CHECK (shipping_cost_usd >= 0),
    transportation_mode VARCHAR(20) NOT NULL,
    delivery_time_days INTEGER DEFAULT 0 CHECK (delivery_time_days >= 0),
    on_time_delivery_rate DECIMAL(5,2) DEFAULT 0 CHECK (on_time_delivery_rate >= 0 AND on_time_delivery_rate <= 100),
    supply_disruption_risk DECIMAL(5,2) DEFAULT 0 CHECK (supply_disruption_risk >= 0 AND supply_disruption_risk <= 100),
    supply_chain_efficiency DECIMAL(5,2) DEFAULT 0 CHECK (supply_chain_efficiency >= 0 AND supply_chain_efficiency <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, supplier_id, warehouse_id)
);

-- Índices para logística
CREATE INDEX IF NOT EXISTS idx_logistics_product ON logistics(product_id);
CREATE INDEX IF NOT EXISTS idx_logistics_supplier ON logistics(supplier_id);
CREATE INDEX IF NOT EXISTS idx_logistics_warehouse ON logistics(warehouse_id);

-- =============================================
-- 7. TABLA: SUPPLY_CHAIN_METRICS
-- =============================================
CREATE TABLE IF NOT EXISTS supply_chain_metrics (
    metric_id SERIAL PRIMARY KEY,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    inventory_optimization_score DECIMAL(5,2) CHECK (inventory_optimization_score >= 0 AND inventory_optimization_score <= 100),
    supplier_performance_score DECIMAL(5,2) CHECK (supplier_performance_score >= 0 AND supplier_performance_score <= 100),
    supply_chain_efficiency DECIMAL(5,2) CHECK (supply_chain_efficiency >= 0 AND supply_chain_efficiency <= 100),
    sustainability_score DECIMAL(5,2) CHECK (sustainability_score >= 0 AND sustainability_score <= 100),
    operational_risk_score DECIMAL(5,2) CHECK (operational_risk_score >= 0 AND operational_risk_score <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para métricas
CREATE INDEX IF NOT EXISTS idx_metrics_product ON supply_chain_metrics(product_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON supply_chain_metrics(date);

-- =============================================
-- VISTAS ÚTILES PARA ANÁLISIS
-- =============================================

-- Vista 1: Stock crítico (productos con stock bajo el punto de reorden)
CREATE OR REPLACE VIEW v_critical_stock AS
SELECT
    p.product_id,
    p.product_category,
    p.brand,
    i.current_stock,
    i.reorder_level,
    i.safety_stock,
    i.warehouse_id,
    w.warehouse_location,
    (i.current_stock - i.reorder_level) AS stock_gap
FROM inventory i
JOIN products p ON i.product_id = p.product_id
JOIN warehouses w ON i.warehouse_id = w.warehouse_id
WHERE i.current_stock < i.reorder_level
ORDER BY stock_gap ASC;

-- Vista 2: Rendimiento de productos por categoría
CREATE OR REPLACE VIEW v_product_performance AS
SELECT
    p.product_id,
    p.product_category,
    p.brand,
    COUNT(s.sales_id) AS num_sales,
    SUM(s.units_sold) AS total_units_sold,
    SUM(s.revenue_usd) AS total_revenue,
    SUM(s.profit_usd) AS total_profit,
    AVG(s.profit_usd) AS avg_profit_per_sale,
    AVG(i.inventory_optimization_score) AS avg_optimization_score,
    AVG(i.operational_risk_score) AS avg_risk_score
FROM products p
LEFT JOIN sales s ON p.product_id = s.product_id
LEFT JOIN inventory i ON p.product_id = i.product_id
GROUP BY p.product_id, p.product_category, p.brand;

-- Vista 3: Eficiencia de proveedores
CREATE OR REPLACE VIEW v_supplier_efficiency AS
SELECT
    s.supplier_id,
    s.supplier_rating,
    s.supplier_performance_score,
    s.sustainability_score,
    AVG(l.on_time_delivery_rate) AS avg_on_time_delivery,
    AVG(l.delivery_time_days) AS avg_delivery_days,
    COUNT(DISTINCT l.product_id) AS products_supplied
FROM suppliers s
JOIN logistics l ON s.supplier_id = l.supplier_id
GROUP BY s.supplier_id, s.supplier_rating, s.supplier_performance_score, s.sustainability_score;

-- =============================================
-- FUNCIONES Y TRIGGERS
-- =============================================

-- Función para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Aplicar trigger a tablas con updated_at
CREATE OR REPLACE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_suppliers_updated_at BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_warehouses_updated_at BEFORE UPDATE ON warehouses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_inventory_updated_at BEFORE UPDATE ON inventory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_logistics_updated_at BEFORE UPDATE ON logistics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- FUNCIÓN: Calcular métricas de riesgo
-- =============================================
CREATE OR REPLACE FUNCTION calculate_risk_score(
    stock_level INTEGER,
    reorder_level INTEGER,
    safety_stock INTEGER,
    turnover DECIMAL
) RETURNS DECIMAL AS $$
DECLARE
    risk_score DECIMAL;
BEGIN
    -- Fórmula simple de riesgo combinado
    risk_score := 100 - (
        (stock_level::DECIMAL / NULLIF(reorder_level, 0) * 30) +
        (safety_stock::DECIMAL / NULLIF(reorder_level, 0) * 30) +
        (turnover * 2)
    );
    -- Limitar entre 0 y 100
    RETURN GREATEST(0, LEAST(100, risk_score));
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- MENSAJE DE CONFIRMACIÓN
-- =============================================
DO $$
BEGIN
    RAISE NOTICE ' Base de datos Supply Chain creada correctamente';
    RAISE NOTICE ' Tablas creadas: products, suppliers, warehouses, inventory, sales, logistics, supply_chain_metrics';
    RAISE NOTICE ' Vistas creadas: v_critical_stock, v_product_performance, v_supplier_efficiency';
END $$;
