-- Proyecto Jupiter: esquema operativo y migracion idempotente.
BEGIN;

-- Esquema analitico local conservado.
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

CREATE TABLE IF NOT EXISTS public.users (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    descripcion VARCHAR(200) NOT NULL,
    password VARCHAR(255) NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    startline TIMESTAMPTZ,
    deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    auth_provider VARCHAR(40) NOT NULL DEFAULT 'local',
    google_sub VARCHAR(255),
    avatar_url TEXT,
    given_name VARCHAR(255),
    family_name VARCHAR(255),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at TIMESTAMPTZ
);

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(40) NOT NULL DEFAULT 'local';

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255);

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS avatar_url TEXT;

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS given_name VARCHAR(255);

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS family_name VARCHAR(255);

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_google_sub
    ON public.users (google_sub)
    WHERE google_sub IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.proms (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name VARCHAR(150),
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.productos (
    pk_product BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    cdgo_producto_externo VARCHAR(200),
    name_product VARCHAR(200) NOT NULL,
    description_product VARCHAR(1000),
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    price NUMERIC(18,4) DEFAULT 0,
    unit INTEGER NOT NULL DEFAULT 1,
    final_price NUMERIC(18,4) DEFAULT 0,
    discount NUMERIC(18,4) DEFAULT 0,
    discount_end_date TIMESTAMPTZ,
    fk_currency INTEGER NOT NULL DEFAULT 1,
    currency VARCHAR(50),
    user_rating NUMERIC(10,2) NOT NULL DEFAULT 0,
    link VARCHAR(255),
    creation_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fk_last_update_user BIGINT NOT NULL DEFAULT 1,
    last_update TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    supplier VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS public.products_images (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id BIGINT REFERENCES public.productos(pk_product) ON DELETE SET NULL,
    original_filename VARCHAR(255),
    stored_filename VARCHAR(255) NOT NULL UNIQUE,
    mime_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    public_url TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_products_images_product_id
    ON public.products_images (product_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_products_images_default_per_product
    ON public.products_images (product_id)
    WHERE is_default = TRUE;

CREATE TABLE IF NOT EXISTS public.inventory_units (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_currencies (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    iso_code CHAR(3) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    symbol VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_exchange_rates (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    currency_id BIGINT NOT NULL REFERENCES public.inventory_currencies(id) ON UPDATE CASCADE,
    rate_to_base NUMERIC(18,6) NOT NULL,
    effective_date DATE NOT NULL,
    source VARCHAR(120),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(currency_id, effective_date)
);

CREATE TABLE IF NOT EXISTS public.inventory_unit_conversions (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id BIGINT REFERENCES public.productos(pk_product) ON DELETE CASCADE,
    from_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    to_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    factor NUMERIC(18,6) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, from_unit_id, to_unit_id)
);

CREATE TABLE IF NOT EXISTS public.inventory_warehouses (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.product_inventory_config (
    product_id BIGINT PRIMARY KEY REFERENCES public.productos(pk_product) ON DELETE CASCADE,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    reorder_point NUMERIC(18,4) NOT NULL DEFAULT 0,
    reorder_quantity NUMERIC(18,4) NOT NULL DEFAULT 0,
    allow_negative_stock BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_suppliers (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    supplier_code VARCHAR(80) UNIQUE,
    name VARCHAR(200) NOT NULL UNIQUE,
    email VARCHAR(255),
    phone VARCHAR(80),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_stock_levels (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON DELETE CASCADE,
    physical_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    reserved_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS public.purchase_orders (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES public.inventory_suppliers(id) ON UPDATE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    purchase_order_number VARCHAR(80) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.purchase_order_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES public.purchase_orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    requested_qty NUMERIC(18,4) NOT NULL,
    received_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    canceled_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    pending_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    currency_id BIGINT NOT NULL REFERENCES public.inventory_currencies(id) ON UPDATE CASCADE,
    currency_code CHAR(3) NOT NULL,
    unit_price NUMERIC(18,4) NOT NULL DEFAULT 0,
    exchange_rate NUMERIC(18,6) NOT NULL DEFAULT 1,
    exchange_rate_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.goods_receipts (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES public.purchase_orders(id) ON DELETE CASCADE,
    supplier_id BIGINT NOT NULL REFERENCES public.inventory_suppliers(id) ON UPDATE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    receipt_number VARCHAR(80) NOT NULL UNIQUE,
    operation_key VARCHAR(120) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.goods_receipt_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    receipt_id BIGINT NOT NULL REFERENCES public.goods_receipts(id) ON DELETE CASCADE,
    purchase_order_line_id BIGINT NOT NULL REFERENCES public.purchase_order_lines(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    received_qty NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    currency_id BIGINT NOT NULL REFERENCES public.inventory_currencies(id) ON UPDATE CASCADE,
    currency_code CHAR(3) NOT NULL,
    unit_price NUMERIC(18,4) NOT NULL DEFAULT 0,
    exchange_rate NUMERIC(18,6) NOT NULL DEFAULT 1,
    exchange_rate_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_orders (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    customer_name VARCHAR(200) NOT NULL,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    sales_order_number VARCHAR(80) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_order_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    sales_order_id BIGINT NOT NULL REFERENCES public.sales_orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    requested_qty NUMERIC(18,4) NOT NULL,
    reserved_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    dispatched_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    invoiced_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    canceled_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    returned_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    pending_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    currency_id BIGINT NOT NULL REFERENCES public.inventory_currencies(id) ON UPDATE CASCADE,
    currency_code CHAR(3) NOT NULL,
    unit_price NUMERIC(18,4) NOT NULL DEFAULT 0,
    exchange_rate NUMERIC(18,6) NOT NULL DEFAULT 1,
    exchange_rate_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_reservations (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    sales_order_id BIGINT NOT NULL REFERENCES public.sales_orders(id) ON DELETE CASCADE,
    sales_order_line_id BIGINT NOT NULL REFERENCES public.sales_order_lines(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    reserved_qty NUMERIC(18,4) NOT NULL,
    released_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    operation_key VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_dispatches (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    sales_order_id BIGINT NOT NULL REFERENCES public.sales_orders(id) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    dispatch_number VARCHAR(80) NOT NULL UNIQUE,
    operation_key VARCHAR(120) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_dispatch_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    dispatch_id BIGINT NOT NULL REFERENCES public.sales_dispatches(id) ON DELETE CASCADE,
    sales_order_line_id BIGINT NOT NULL REFERENCES public.sales_order_lines(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    dispatched_qty NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_invoices (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    sales_order_id BIGINT NOT NULL REFERENCES public.sales_orders(id) ON DELETE CASCADE,
    invoice_number VARCHAR(80) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_invoice_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES public.sales_invoices(id) ON DELETE CASCADE,
    sales_order_line_id BIGINT NOT NULL REFERENCES public.sales_order_lines(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    invoiced_qty NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_returns (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    sales_order_id BIGINT NOT NULL REFERENCES public.sales_orders(id) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    return_number VARCHAR(80) NOT NULL UNIQUE,
    credit_note_number VARCHAR(80) NOT NULL UNIQUE,
    operation_key VARCHAR(120) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    reason VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sales_return_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    sales_return_id BIGINT NOT NULL REFERENCES public.sales_returns(id) ON DELETE CASCADE,
    sales_order_line_id BIGINT NOT NULL REFERENCES public.sales_order_lines(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    returned_qty NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_transfers (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    source_warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    destination_warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    transfer_number VARCHAR(80) NOT NULL UNIQUE,
    operation_key VARCHAR(120) NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'borrador',
    user_name VARCHAR(120) NOT NULL,
    reason VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_transfer_lines (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    transfer_id BIGINT NOT NULL REFERENCES public.inventory_transfers(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    quantity NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_movements (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    movement_type VARCHAR(60) NOT NULL,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON UPDATE CASCADE,
    warehouse_id BIGINT REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    warehouse_destination_id BIGINT REFERENCES public.inventory_warehouses(id) ON UPDATE CASCADE,
    quantity NUMERIC(18,4) NOT NULL,
    quantity_signed NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    document_type VARCHAR(60),
    document_id BIGINT,
    document_line_id BIGINT,
    operation_key VARCHAR(120) NOT NULL,
    reason VARCHAR(120),
    user_name VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.external_data_cache (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    source VARCHAR(80) NOT NULL,
    operation VARCHAR(80) NOT NULL,
    cache_key VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    country CHAR(2),
    currency CHAR(3),
    reference_url TEXT,
    queried_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE(source, operation, cache_key)
);

CREATE TABLE IF NOT EXISTS public.review_batches (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON DELETE CASCADE,
    source VARCHAR(80) NOT NULL,
    country CHAR(2),
    currency CHAR(3),
    status VARCHAR(30) NOT NULL,
    total_reviews INTEGER NOT NULL DEFAULT 0,
    summary JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.product_reviews (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES public.review_batches(id) ON DELETE CASCADE,
    source_review_id VARCHAR(255),
    rating NUMERIC(3,2),
    review_text TEXT NOT NULL,
    sentiment VARCHAR(20) NOT NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.knowledge_documents (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(120) NOT NULL,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_inventory_stock_levels_product_warehouse
    ON public.inventory_stock_levels (product_id, warehouse_id);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_product_warehouse
    ON public.inventory_movements (product_id, warehouse_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_external_data_cache_source_expiry
    ON public.external_data_cache (source, expires_at DESC);

CREATE INDEX IF NOT EXISTS ix_product_reviews_batch
    ON public.product_reviews (batch_id);

CREATE INDEX IF NOT EXISTS ix_knowledge_documents_active_expiry
    ON public.knowledge_documents (is_active, expires_at);

INSERT INTO public.inventory_units (code, name, description)
VALUES
    ('unit', 'Unidad', 'Unidad base'),
    ('box', 'Caja', 'Caja o empaque'),
    ('kg', 'Kilogramo', 'Unidad de peso')
ON CONFLICT (code) DO NOTHING;

INSERT INTO public.inventory_currencies (iso_code, name, symbol)
VALUES
    ('EUR', 'Euro', '€'),
    ('USD', 'US Dollar', '$'),
    ('COP', 'Peso Colombiano', '$')
ON CONFLICT (iso_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.agent_decisions (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    requested_agent VARCHAR(50), routed_agent VARCHAR(50) NOT NULL,
    request_data JSONB NOT NULL, response_summary JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.automation_rules (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    code VARCHAR(80) NOT NULL UNIQUE, name VARCHAR(160) NOT NULL, description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE, interval_minutes INTEGER NOT NULL DEFAULT 1440,
    last_run_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.automation_runs (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    rule_id BIGINT NOT NULL REFERENCES public.automation_rules(id) ON DELETE CASCADE,
    initiated_by VARCHAR(80) NOT NULL, status VARCHAR(30) NOT NULL,
    result JSONB, error_message VARCHAR(500), started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.purchase_proposals (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    automation_run_id BIGINT REFERENCES public.automation_runs(id) ON DELETE SET NULL,
    product_id BIGINT NOT NULL REFERENCES public.productos(pk_product) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON DELETE CASCADE,
    suggested_qty NUMERIC(18,4) NOT NULL, base_unit_code VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending_approval', justification TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_automation_runs_rule_started
    ON public.automation_runs (rule_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_purchase_proposals_pending
    ON public.purchase_proposals (status, product_id, warehouse_id);

-- Cuenta inicial para el acceso local. La contraseña se almacena con PBKDF2.
INSERT INTO public.users (
    nombre,
    apellido,
    email,
    descripcion,
    password,
    status,
    auth_provider,
    email_verified
)
VALUES (
    'Administrador',
    'Local',
    'admin@stockassistant.app',
    'Cuenta local de administracion de Proyecto Jupiter',
    'pbkdf2_sha256$150000$W-hlMXWZEWti4S9MffIs2Q$ZtbTCJr0CBw4jnULU1E81snKcz25w3HjzMw44pujhkM',
    1,
    'local',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    password = EXCLUDED.password, status = 1, auth_provider = 'local', email_verified = TRUE;

COMMIT;
