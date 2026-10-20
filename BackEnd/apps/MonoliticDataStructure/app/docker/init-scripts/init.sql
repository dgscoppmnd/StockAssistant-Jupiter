-- Proyecto Jupiter: fuente unica de creacion y actualizacion del esquema.
-- Aplica sobre la base conectada: no crea ni elimina bases.
-- El bloque PRODUCTS UNIFICATION sustituye las tablas antiguas tras copiar sus
-- datos y reasignar sus dependencias, dentro de la misma transacción.
BEGIN;
-- BEGIN JUPITER SCHEMA

-- Last confirmed manual schema update; written atomically by the Setup operation.
CREATE TABLE IF NOT EXISTS public.app_schema_updates (
    id SMALLINT PRIMARY KEY CHECK (id=1),
    checksum VARCHAR(64) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    actor_id BIGINT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    statement_count INTEGER NOT NULL,
    validated_constraints INTEGER NOT NULL
);
REVOKE ALL ON public.app_schema_updates FROM PUBLIC;
-- Durable execution ledger: a previously applied file must never run again.
CREATE TABLE IF NOT EXISTS public.app_schema_update_history (
    checksum VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL,
    statement_count INTEGER NOT NULL,
    validated_constraints INTEGER NOT NULL
);
INSERT INTO public.app_schema_update_history
    (checksum,run_id,applied_at,statement_count,validated_constraints)
SELECT checksum,run_id,applied_at,statement_count,validated_constraints
FROM public.app_schema_updates ON CONFLICT (checksum) DO NOTHING;
REVOKE ALL ON public.app_schema_update_history FROM PUBLIC;
DO $schema_update_permissions$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app') THEN
        REVOKE INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER ON public.app_schema_updates FROM app;
        GRANT SELECT ON public.app_schema_updates TO app;
        REVOKE INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER ON public.app_schema_update_history FROM app;
        GRANT SELECT ON public.app_schema_update_history TO app;
    END IF;
END;
$schema_update_permissions$;

-- Esquema analitico local conservado.
-- Conectar a la base de datos

-- Habilitar extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================
-- 1. TABLA: PRODUCTS
-- =============================================
-- BEGIN PRODUCTS UNIFICATION
-- Maintenance-window migration. Run as schema owner/migrator, never as the app role.
-- Both entry points (psql and schema_sql()) execute this in the enclosing transaction.
SELECT pg_advisory_xact_lock(702641903119);
SET LOCAL lock_timeout = '15s';
DO $unify_products$
DECLARE
    operational_oid oid;
    analytical_oid oid;
    dependency record;
    permission record;
    high_id bigint;
BEGIN
    SELECT oid INTO operational_oid FROM pg_class
      WHERE oid=to_regclass('public.productos') AND relkind='r';
    SELECT c.oid INTO analytical_oid FROM pg_class c
      WHERE c.oid=to_regclass('public.products') AND c.relkind='r'
      AND NOT EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid
                      AND a.attname='id' AND NOT a.attisdropped);
    IF operational_oid IS NULL AND analytical_oid IS NULL THEN RETURN; END IF;
    IF to_regclass('public.products') IS NOT NULL AND analytical_oid IS NULL THEN
        RAISE EXCEPTION 'Mixed canonical/legacy products schema; reconcile before migration';
    END IF;
    IF analytical_oid IS NOT NULL THEN
        LOCK TABLE public.products IN ACCESS EXCLUSIVE MODE;
        -- Supported pre-semantic installations did not have these columns yet.
        ALTER TABLE public.products ADD COLUMN IF NOT EXISTS product_name varchar(150) NOT NULL DEFAULT '';
        ALTER TABLE public.products ADD COLUMN IF NOT EXISTS description varchar(500) NOT NULL DEFAULT '';
    END IF;
    IF operational_oid IS NOT NULL THEN LOCK TABLE public.productos IN ACCESS EXCLUSIVE MODE; END IF;
    -- Unknown database-side business rules must be ported explicitly. Dropping
    -- a legacy table must never silently remove custom triggers, RLS or checks.
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid IN (operational_oid,analytical_oid)
               AND NOT tgisinternal
               AND tgname NOT IN ('update_products_updated_at','trg_update_last_update'))
       OR EXISTS (SELECT 1 FROM pg_class WHERE oid IN (operational_oid,analytical_oid)
                  AND (relrowsecurity OR relforcerowsecurity))
       OR EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid IN (operational_oid,analytical_oid)
                  AND contype IN ('c','f','x')
                  AND conname NOT IN ('products_product_cost_usd_check','products_selling_price_usd_check')) THEN
        RAISE EXCEPTION 'Custom product trigger, policy or constraint requires an explicit migration; migration rolled back';
    END IF;
    -- Do not guess how two conflicting catalog records should be merged.
    IF operational_oid IS NOT NULL AND analytical_oid IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM public.products a JOIN public.productos o
                   ON a.product_id=o.cdgo_producto_externo
                   WHERE (NULLIF(a.product_name,'') IS NOT NULL AND a.product_name<>o.name_product)
                      OR (NULLIF(a.description,'') IS NOT NULL
                          AND NULLIF(o.description_product,'') IS NOT NULL
                          AND a.description<>o.description_product)) THEN
            RAISE EXCEPTION 'Conflicting product name/description for the same external code; migration rolled back';
        END IF;
    END IF;
    CREATE TABLE public.products_unified (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(200) UNIQUE,
    product_name VARCHAR(200) NOT NULL,
    description TEXT,
    product_category VARCHAR(50),
    brand VARCHAR(50),
    sku VARCHAR(50) UNIQUE,
    product_cost_usd NUMERIC(18,4) CHECK (product_cost_usd >= 0),
    selling_price_usd NUMERIC(18,4) CHECK (selling_price_usd >= 0),
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
    fk_last_update_user BIGINT NOT NULL DEFAULT 1,
    supplier VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
    IF operational_oid IS NOT NULL THEN
        INSERT INTO public.products_unified
          (id,product_id,product_name,description,disabled,price,unit,final_price,discount,
           discount_end_date,fk_currency,currency,user_rating,link,created_at,
           fk_last_update_user,updated_at,supplier)
        SELECT pk_product,cdgo_producto_externo,name_product,description_product,disabled,
               price,unit,final_price,discount,discount_end_date,fk_currency,currency,
               user_rating,link,creation_date,fk_last_update_user,last_update,supplier
        FROM public.productos;
    END IF;
    SELECT COALESCE(max(id),0) INTO high_id FROM public.products_unified;
    IF analytical_oid IS NOT NULL THEN
        UPDATE public.products_unified u SET
          description=COALESCE(NULLIF(u.description,''),a.description),
          product_category=a.product_category,brand=a.brand,sku=a.sku,
          product_cost_usd=a.product_cost_usd,selling_price_usd=a.selling_price_usd
        FROM public.products a WHERE u.product_id=a.product_id;
        INSERT INTO public.products_unified
          (id,product_id,product_name,description,product_category,brand,sku,
           product_cost_usd,selling_price_usd,price,final_price,currency,created_at,updated_at)
        SELECT high_id+row_number() OVER (ORDER BY a.product_id),a.product_id,
               a.product_name,a.description,a.product_category,a.brand,a.sku,
               a.product_cost_usd,a.selling_price_usd,a.selling_price_usd,
               a.selling_price_usd,'USD',a.created_at,a.updated_at
        FROM public.products a WHERE NOT EXISTS
          (SELECT 1 FROM public.products_unified u WHERE u.product_id=a.product_id);
    END IF;
    -- Keep the legacy timestamp interpretation explicit; no silent session-zone conversion.
    -- The caller must set TimeZone to the zone used when analytical TIMESTAMP values were written.
    -- Preserve all FK actions, names and deferrability; do not use DROP ... CASCADE.
    FOR dependency IN SELECT conrelid::regclass AS child,conname,confrelid,
                              pg_get_constraintdef(oid) AS definition
                      FROM pg_constraint WHERE contype='f'
                      AND confrelid IN (operational_oid,analytical_oid)
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I',dependency.child,dependency.conname);
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s',dependency.child,dependency.conname,
          regexp_replace(dependency.definition,'REFERENCES [^(]+\([^)]*\)',
            CASE WHEN dependency.confrelid=operational_oid
                 THEN 'REFERENCES public.products_unified(id)'
                 ELSE 'REFERENCES public.products_unified(product_id)' END));
    END LOOP;
    -- Preserve explicit application grants as well as migrator default privileges.
    FOR permission IN SELECT DISTINCT grantee,privilege_type FROM information_schema.role_table_grants
                      WHERE table_schema='public' AND table_name IN ('products','productos')
    LOOP
        EXECUTE format('GRANT %s ON public.products_unified TO %s',permission.privilege_type,
          CASE WHEN permission.grantee='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(permission.grantee) END);
        IF permission.privilege_type='INSERT' THEN
            EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE public.products_unified_id_seq TO %s',
              CASE WHEN permission.grantee='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(permission.grantee) END);
        END IF;
    END LOOP;
    DROP VIEW IF EXISTS public.productos_catalogo;
    DROP VIEW IF EXISTS public.ultimos_productos_creados;
    DROP VIEW IF EXISTS public.v_critical_stock;
    DROP VIEW IF EXISTS public.v_product_performance;
    IF operational_oid IS NOT NULL THEN DROP TABLE public.productos; END IF;
    IF analytical_oid IS NOT NULL THEN DROP TABLE public.products; END IF;
    ALTER TABLE public.products_unified RENAME TO products;
    SELECT COALESCE(max(id),0) INTO high_id FROM public.products;
    PERFORM setval(pg_get_serial_sequence('public.products','id'),GREATEST(high_id,1),high_id>0);
END;
$unify_products$;
-- END PRODUCTS UNIFICATION

CREATE TABLE IF NOT EXISTS products (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(200) UNIQUE,
    product_name VARCHAR(200) NOT NULL,
    description TEXT,
    product_category VARCHAR(50),
    brand VARCHAR(50),
    sku VARCHAR(50) UNIQUE,
    product_cost_usd NUMERIC(18,4) CHECK (product_cost_usd >= 0),
    selling_price_usd NUMERIC(18,4) CHECK (selling_price_usd >= 0),
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
    fk_last_update_user BIGINT NOT NULL DEFAULT 1,
    supplier VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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
    p.product_id::varchar(200) AS product_id,
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
    p.product_id::varchar(200) AS product_id,
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

CREATE TABLE IF NOT EXISTS public.chat_conversations (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    agent_key VARCHAR(80) NOT NULL DEFAULT 'stockassistant',
    title VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_chat_conversations_user_updated
    ON public.chat_conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.chat_messages (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES public.chat_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_created
    ON public.chat_messages (conversation_id, created_at, id);

CREATE TABLE IF NOT EXISTS public.proms (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name VARCHAR(150),
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE VIEW public.productos AS
SELECT id AS pk_product, product_id AS cdgo_producto_externo,
       product_name AS name_product, description AS description_product,
       disabled, price, unit, final_price, discount, discount_end_date,
       fk_currency, currency, user_rating, link, created_at AS creation_date,
       fk_last_update_user, updated_at AS last_update, supplier,
       product_category, brand, sku, product_cost_usd, selling_price_usd
FROM public.products;

-- Preserve DML access to the compatibility contract, including installations
-- whose application grants predate ALTER DEFAULT PRIVILEGES.
DO $product_view_permissions$
DECLARE permission record;
BEGIN
    FOR permission IN SELECT DISTINCT grantee,privilege_type
                      FROM information_schema.role_table_grants
                      WHERE table_schema='public' AND table_name='products'
                      AND privilege_type IN ('SELECT','INSERT','UPDATE','DELETE')
    LOOP
        EXECUTE format('GRANT %s ON public.productos TO %s',permission.privilege_type,
          CASE WHEN permission.grantee='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(permission.grantee) END);
    END LOOP;
END;
$product_view_permissions$;

CREATE TABLE IF NOT EXISTS public.products_images (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id BIGINT REFERENCES public.products(id) ON DELETE SET NULL,
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
    product_id BIGINT REFERENCES public.products(id) ON DELETE CASCADE,
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
    product_id BIGINT PRIMARY KEY REFERENCES public.products(id) ON DELETE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
    quantity NUMERIC(18,4) NOT NULL,
    base_unit_id BIGINT NOT NULL REFERENCES public.inventory_units(id) ON UPDATE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.inventory_movements (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    movement_type VARCHAR(60) NOT NULL,
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE,
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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
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

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS archivo TEXT;

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
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id) ON DELETE CASCADE,
    suggested_qty NUMERIC(18,4) NOT NULL, base_unit_code VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending_approval', justification TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_automation_runs_rule_started
    ON public.automation_runs (rule_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_purchase_proposals_pending
    ON public.purchase_proposals (status, product_id, warehouse_id);

-- Proyecto Jupiter: clientes, direcciones y esquema comercial (2026-09-08).
-- BEGIN SCHEMA EXTENSIONS
-- Proyecto Jupiter: clientes, direcciones y esquema comercial (2026-09-08).
CREATE TABLE IF NOT EXISTS public.type_client (
    pk_type_client BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name VARCHAR(250) NOT NULL
);

INSERT INTO public.type_client (pk_type_client, name) VALUES
    (1, 'Propio'), (2, 'Prospecto'), (3, 'Confirmado'),
    (4, 'Activo'), (5, 'Desactivado'), (6, 'Suspendido')
ON CONFLICT (pk_type_client) DO NOTHING;

SELECT setval(
    pg_get_serial_sequence('public.type_client', 'pk_type_client'),
    GREATEST((SELECT COALESCE(MAX(pk_type_client), 1) FROM public.type_client), 1), true
);

CREATE TABLE IF NOT EXISTS public.clients (
    pk_client BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    client_code TEXT,
    name VARCHAR(250) NOT NULL,
    description VARCHAR(255),
    fk_type_client BIGINT NOT NULL DEFAULT 1 CONSTRAINT fk_clients_type_client REFERENCES public.type_client(pk_type_client) ON UPDATE CASCADE ON DELETE RESTRICT,
    creation_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fk_last_update_user BIGINT DEFAULT 1
);

ALTER TABLE public.clients ADD COLUMN IF NOT EXISTS client_code TEXT;

CREATE TABLE IF NOT EXISTS public.globlal_addresses (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    address_line_1 VARCHAR(255) NOT NULL, address_line_2 VARCHAR(255), city VARCHAR(120) NOT NULL,
    state_province VARCHAR(120), postal_code VARCHAR(32), country_code CHAR(2) NOT NULL,
    country_name VARCHAR(120), latitude NUMERIC(10,7), longitude NUMERIC(10,7),
    contact_name VARCHAR(200), contact_phone VARCHAR(80), contact_email VARCHAR(255), notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.clients_addresses (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES public.clients(pk_client) ON DELETE CASCADE,
    global_address_id BIGINT NOT NULL REFERENCES public.globlal_addresses(id) ON DELETE RESTRICT,
    address_type VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_clients_addresses_type CHECK (address_type IN ('Dirección principal', 'Dirección por defecto', 'Dirección de entrega', 'Dirección de Recogida')),
    UNIQUE (client_id, global_address_id, address_type)
);

CREATE INDEX IF NOT EXISTS ix_clients_addresses_client_id ON public.clients_addresses (client_id);

CREATE INDEX IF NOT EXISTS ix_clients_addresses_global_address_id ON public.clients_addresses (global_address_id);

CREATE TABLE IF NOT EXISTS public.inventory_suppliers_addresses (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES public.inventory_suppliers(id) ON DELETE CASCADE,
    global_address_id BIGINT NOT NULL REFERENCES public.globlal_addresses(id) ON DELETE RESTRICT,
    address_type VARCHAR(40) NOT NULL CHECK (address_type IN ('Dirección principal', 'Dirección por defecto', 'Dirección de entrega', 'Dirección de Recogida')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (supplier_id, global_address_id, address_type)
);

CREATE INDEX IF NOT EXISTS ix_inventory_suppliers_addresses_supplier_id ON public.inventory_suppliers_addresses (supplier_id);

CREATE TABLE IF NOT EXISTS public.error_log
    (
        pk_error BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        error_title character varying COLLATE pg_catalog."default",
        error_description character varying COLLATE pg_catalog."default",
        create_date timestamp with time zone,
        pfk_user integer
    );

CREATE TABLE IF NOT EXISTS public.properties
    (
        id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        property character varying(500) COLLATE pg_catalog."default" NOT NULL,
        value character varying(500) COLLATE pg_catalog."default",
        valueint bigint,
        valuedate timestamp without time zone,
        creation_date timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fk_last_update_user bigint NOT NULL DEFAULT 1,
        last_update timestamp with time zone,
        CONSTRAINT propertyunique UNIQUE (property)
    );

CREATE TABLE IF NOT EXISTS public.currency
    (
        pk_currency BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name character varying(250) COLLATE pg_catalog."default",
        symbol character varying(3) COLLATE pg_catalog."default"
    );

CREATE TABLE IF NOT EXISTS public.type_catalog
    (
        pk_type_catalog BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name character varying(250) COLLATE pg_catalog."default"
    );

CREATE TABLE IF NOT EXISTS public.type_funding_source
    (
        pk_type_funding_source BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name character varying(250) COLLATE pg_catalog."default"
    );

CREATE TABLE IF NOT EXISTS public.catalogues
    (
        pk_catalog BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name_catalog character varying(250) COLLATE pg_catalog."default" NOT NULL,
        start_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        end_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fk_type_catalog integer DEFAULT 1,
        creation_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fk_last_update_user bigint DEFAULT 1
    );

CREATE TABLE IF NOT EXISTS public.catalogues_products
    (
        pk_catalog_product BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        pk_catalog bigint NOT NULL,
        pk_product bigint NOT NULL,
        creation_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fk_last_update_user bigint NOT NULL DEFAULT 1
    );

CREATE TABLE IF NOT EXISTS public.markets
    (
        pk_market BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name_market character varying COLLATE pg_catalog."default",
        disabled boolean NOT NULL DEFAULT false,
        link TEXT,
        description character varying(255) COLLATE pg_catalog."default",
        creation_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fk_last_update_user bigint DEFAULT 1
    );

CREATE TABLE IF NOT EXISTS public.markets_catalogues
    (
        pk_market_catalog BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        fk_market bigint NOT NULL DEFAULT 1,
        fk_catalog bigint NOT NULL DEFAULT 1,
        disabled boolean DEFAULT false,
        fk_client_origin bigint,
        fk_client_destination bigint,
        fk_type_funding_source integer DEFAULT 1,
        creation_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_update TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fk_last_update_user bigint DEFAULT 1
	);

CREATE INDEX IF NOT EXISTS ix_inventory_suppliers_addresses_global_address_id ON public.inventory_suppliers_addresses(global_address_id);

ALTER TABLE public.proms ADD COLUMN IF NOT EXISTS id_prom BIGINT GENERATED ALWAYS AS (id) STORED;

CREATE UNIQUE INDEX IF NOT EXISTS ux_proms_id_prom ON public.proms(id_prom);

ALTER TABLE public.proms ADD COLUMN IF NOT EXISTS nombre VARCHAR(250);

ALTER TABLE public.proms ADD COLUMN IF NOT EXISTS prom TEXT;

ALTER TABLE public.proms ADD COLUMN IF NOT EXISTS status INTEGER DEFAULT 0;

-- External codes are unique in the canonical products table (NULL remains allowed).

CREATE OR REPLACE VIEW public.ultimos_productos_creados
    AS
    WITH max_date AS (
            SELECT max(productos.last_update) AS max_last_update
            FROM productos
            )
    SELECT TRIM(BOTH FROM p.cdgo_producto_externo) AS cdgo_producto_externo,
        TRIM(BOTH FROM p.name_product) AS name_product,
        TRIM(BOTH FROM p.description_product) AS description_product,
        TRIM(BOTH FROM p.supplier) AS supplier,
        p.last_update
    FROM productos p
        JOIN max_date md ON p.last_update >= (md.max_last_update - '2 days'::interval) AND p.last_update <= CURRENT_TIMESTAMP
    ORDER BY (TRIM(BOTH FROM p.cdgo_producto_externo)) DESC;

CREATE OR REPLACE FUNCTION public.set_last_update_timestamp()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Al crear el registro: poner ambas fechas si vienen nulas
        IF NEW.created_at IS NULL THEN
            NEW.created_at := CURRENT_TIMESTAMP;
        END IF;

        IF NEW.updated_at IS NULL THEN
            NEW.updated_at := CURRENT_TIMESTAMP;
        END IF;

    ELSIF TG_OP = 'UPDATE' THEN
        -- En actualización: mantener la fecha de creación
        NEW.created_at := OLD.created_at;

        -- y actualizar solo la de última modificación
        NEW.updated_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_update_last_update BEFORE INSERT OR UPDATE ON public.products FOR EACH ROW EXECUTE FUNCTION public.set_last_update_timestamp();
-- END SCHEMA EXTENSIONS

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
ON CONFLICT (email) DO NOTHING;

-- BEGIN RAG SCHEMA
ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS index_status TEXT NOT NULL DEFAULT 'pending';

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS index_error TEXT;

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS index_revision INTEGER NOT NULL DEFAULT 1;

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS content_hash TEXT;

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS index_progress SMALLINT NOT NULL DEFAULT 0;

ALTER TABLE public.knowledge_documents DROP CONSTRAINT IF EXISTS ck_knowledge_documents_index_progress;

ALTER TABLE public.knowledge_documents ADD CONSTRAINT ck_knowledge_documents_index_progress CHECK (index_progress BETWEEN 0 AND 100);

CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
            id UUID PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES public.knowledge_documents(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL,
            page INTEGER,
            content TEXT NOT NULL,
            embedding_provider TEXT NOT NULL DEFAULT 'ollama',
            embedding_model TEXT NOT NULL
        );

ALTER TABLE public.knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_provider TEXT NOT NULL DEFAULT 'ollama';

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS index_embedding_provider TEXT;

ALTER TABLE public.knowledge_documents ADD COLUMN IF NOT EXISTS index_embedding_model TEXT;

CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_document ON public.knowledge_chunks(document_id, revision);

CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_profile ON public.knowledge_chunks(embedding_provider, embedding_model);

CREATE OR REPLACE FUNCTION public.invalidate_knowledge_index() RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.archivo IS DISTINCT FROM OLD.archivo OR NEW.content IS DISTINCT FROM OLD.content
               OR NEW.title IS DISTINCT FROM OLD.title
               OR NEW.is_active IS DISTINCT FROM OLD.is_active
               OR NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
                NEW.index_status := 'pending';
                NEW.index_error := NULL;
                NEW.index_progress := 0;
                NEW.index_revision := OLD.index_revision + 1;
                NEW.content_hash := NULL;
                DELETE FROM public.knowledge_chunks WHERE document_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS knowledge_document_changed ON public.knowledge_documents;

CREATE TRIGGER knowledge_document_changed BEFORE UPDATE ON public.knowledge_documents
            FOR EACH ROW EXECUTE FUNCTION public.invalidate_knowledge_index();

CREATE TABLE IF NOT EXISTS public.knowledge_vector_deletions (
    id UUID PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL
);
CREATE OR REPLACE FUNCTION public.retire_knowledge_vector() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.knowledge_vector_deletions (id, provider, model)
    VALUES (OLD.id, OLD.embedding_provider, OLD.embedding_model) ON CONFLICT DO NOTHING;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS knowledge_chunk_retired ON public.knowledge_chunks;
CREATE TRIGGER knowledge_chunk_retired AFTER DELETE ON public.knowledge_chunks
    FOR EACH ROW EXECUTE FUNCTION public.retire_knowledge_vector();
-- END RAG SCHEMA

-- BEGIN SALES MODULE
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS sales_permissions TEXT[] NOT NULL
    DEFAULT ARRAY['read','create','edit','delete','reserve','dispatch','invoice','void','return'];

ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS client_id BIGINT REFERENCES public.clients(pk_client) ON DELETE RESTRICT;
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS address_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS order_date DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS reference TEXT;
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS currency_code CHAR(3) NOT NULL DEFAULT 'EUR';
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS subtotal NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS tax_total NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_orders ADD COLUMN IF NOT EXISTS total NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_order_lines ADD COLUMN IF NOT EXISTS description_snapshot TEXT;
ALTER TABLE public.sales_order_lines ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(7,4) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_order_lines ADD COLUMN IF NOT EXISTS tax_percent NUMERIC(7,4) NOT NULL DEFAULT 0;

ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS invoice_date DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS due_date DATE;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS reference TEXT;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS customer_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS currency_code CHAR(3) NOT NULL DEFAULT 'EUR';
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS subtotal NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS tax_total NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS total NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS correction_of_id BIGINT REFERENCES public.sales_invoices(id) ON DELETE RESTRICT;
ALTER TABLE public.sales_invoices ADD COLUMN IF NOT EXISTS void_reason TEXT;

ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS description_snapshot TEXT;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS unit_snapshot TEXT;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS unit_price NUMERIC(18,4) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(7,4) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS tax_percent NUMERIC(7,4) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(18,6) NOT NULL DEFAULT 1;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS exchange_rate_date DATE;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS line_subtotal NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS line_tax NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE public.sales_invoice_lines ADD COLUMN IF NOT EXISTS line_total NUMERIC(18,2) NOT NULL DEFAULT 0;

-- Snapshot legacy invoices once; subsequent catalogue changes must not rewrite them.
UPDATE public.sales_invoice_lines il SET
    description_snapshot = p.name_product, unit_snapshot = u.code,
    unit_price = ol.unit_price, exchange_rate = ol.exchange_rate,
    exchange_rate_date = ol.exchange_rate_date,
    line_subtotal = ROUND(il.invoiced_qty * ol.unit_price, 2),
    line_total = ROUND(il.invoiced_qty * ol.unit_price, 2)
FROM public.sales_order_lines ol, public.productos p, public.inventory_units u
WHERE il.sales_order_line_id = ol.id AND il.product_id = p.pk_product
  AND il.base_unit_id = u.id AND il.description_snapshot IS NULL;
UPDATE public.sales_invoices i SET
    customer_snapshot = jsonb_build_object('name', o.customer_name, 'address', o.address_snapshot),
    currency_code = COALESCE((SELECT l.currency_code FROM public.sales_order_lines l
                              WHERE l.sales_order_id = o.id ORDER BY l.id LIMIT 1), o.currency_code),
    subtotal = COALESCE((SELECT SUM(line_subtotal) FROM public.sales_invoice_lines WHERE invoice_id = i.id), 0),
    tax_total = COALESCE((SELECT SUM(line_tax) FROM public.sales_invoice_lines WHERE invoice_id = i.id), 0),
    total = COALESCE((SELECT SUM(line_total) FROM public.sales_invoice_lines WHERE invoice_id = i.id), 0)
FROM public.sales_orders o WHERE i.sales_order_id = o.id AND i.customer_snapshot = '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.sales_document_events (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    document_type TEXT NOT NULL CHECK (document_type IN ('order','invoice')),
    document_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    operation_key VARCHAR(120) NOT NULL UNIQUE,
    payload_hash TEXT NOT NULL,
    user_id BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    user_name TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_sales_events_document ON public.sales_document_events(document_type, document_id, id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_filters ON public.sales_orders(order_date DESC, client_id, status, id);
CREATE INDEX IF NOT EXISTS ix_sales_invoices_filters ON public.sales_invoices(invoice_date DESC, status, sales_order_id, id);
-- END SALES MODULE

-- BEGIN PRODUCT SEARCH
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS ix_products_search_trgm ON public.products USING gin ((translate(lower(coalesce(product_id, '') || ' ' || product_name), 'áàâäãåéèêëíìîïóòôöõúùûüñç', 'aaaaaaeeeeiiiiooooouuuunc')) gin_trgm_ops);
-- END PRODUCT SEARCH

-- BEGIN INTEGRATED AUTOMATION SCHEMA
-- Additive migration; safe to apply to an existing installation.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='users' AND column_name='automation_permissions') THEN
  ALTER TABLE public.users ADD COLUMN automation_permissions JSONB NOT NULL DEFAULT '["read"]';
  UPDATE public.users SET automation_permissions='["read","edit","activate","approve","execute","authorize"]'
  WHERE email='admin@stockassistant.app';
 END IF;
END $$;
ALTER TABLE public.automation_rules ADD COLUMN IF NOT EXISTS current_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.automation_rules ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ;
ALTER TABLE public.automation_rules ADD COLUMN IF NOT EXISTS claim_token TEXT;
ALTER TABLE public.automation_rules ADD COLUMN IF NOT EXISTS failures INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS public.automation_rule_versions (
 rule_id BIGINT NOT NULL REFERENCES public.automation_rules(id), version INTEGER NOT NULL,
 config JSONB NOT NULL, author TEXT NOT NULL, reason TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(rule_id,version)
);
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS rule_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS config_snapshot JSONB;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS claim_token TEXT;
CREATE TABLE IF NOT EXISTS public.automation_events (
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
 run_id BIGINT REFERENCES public.automation_runs(id), rule_id BIGINT REFERENCES public.automation_rules(id),
 phase TEXT NOT NULL, detail JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS automation_events_run ON public.automation_events(run_id,id);
CREATE TABLE IF NOT EXISTS public.agent_action_proposals (
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
 run_id BIGINT NOT NULL REFERENCES public.automation_runs(id), rule_id BIGINT NOT NULL REFERENCES public.automation_rules(id),
 rule_version INTEGER NOT NULL, product_id BIGINT NOT NULL REFERENCES public.products(id),
 warehouse_id BIGINT NOT NULL REFERENCES public.inventory_warehouses(id), action TEXT NOT NULL
 CHECK(action IN ('replenish','transfer','suspend_reorder','promotion','supplier_return')),
 idempotency_key TEXT NOT NULL UNIQUE, plan JSONB NOT NULL, snapshot_hash TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending_approval'
 CHECK(status IN ('pending_approval','approved','executed','rejected','obsolete')), expires_at TIMESTAMPTZ NOT NULL,
 approved_by TEXT, approved_at TIMESTAMPTZ, reason TEXT, executed_by TEXT,
 action_result JSONB, evaluation JSONB, review_at TIMESTAMPTZ NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS agent_action_one_open ON public.agent_action_proposals(product_id,warehouse_id,action)
 WHERE status IN ('pending_approval','approved');
CREATE TABLE IF NOT EXISTS public.automation_control (
 id INTEGER PRIMARY KEY CHECK(id=1), stopped BOOLEAN NOT NULL DEFAULT FALSE, updated_by TEXT, updated_at TIMESTAMPTZ DEFAULT now()
);
INSERT INTO public.automation_control(id) VALUES(1) ON CONFLICT DO NOTHING;
-- Legacy proposals have no evidence snapshot or current policy version and cannot be approved safely.
UPDATE public.purchase_proposals SET status='obsolete',
 justification=justification || ' Requiere nuevo análisis con evidencia y versión de política.'
WHERE status='pending_approval';
-- Older workers may have left runs in running state. Runtime lease recovery handles new runs.
-- END INTEGRATED AUTOMATION SCHEMA
-- BEGIN EXISTING TABLE INTEGRITY MIGRATION
-- Reconcile pre-existing tables; CREATE TABLE IF NOT EXISTS does not apply these changes.
-- Only schema metadata is changed. Invalid existing data aborts the caller's transaction.
-- Native PostgreSQL constraint names match the declarations used for a fresh installation.
DO $integrity_defaults$
DECLARE
    spec RECORD;
    current_default TEXT;
BEGIN
    FOR spec IN SELECT * FROM (VALUES
        ('inventory', 'created_at', 'CURRENT_TIMESTAMP'),
        ('inventory', 'current_stock', '0'),
        ('inventory', 'inventory_optimization_score', '0'),
        ('inventory', 'inventory_turnover', '0'),
        ('inventory', 'operational_risk_score', '0'),
        ('inventory', 'overstock_risk', '0'),
        ('inventory', 'reorder_level', '0'),
        ('inventory', 'safety_stock', '0'),
        ('inventory', 'stockout_risk', '0'),
        ('inventory', 'updated_at', 'CURRENT_TIMESTAMP'),
        ('logistics', 'created_at', 'CURRENT_TIMESTAMP'),
        ('logistics', 'delivery_time_days', '0'),
        ('logistics', 'on_time_delivery_rate', '0'),
        ('logistics', 'shipping_cost_usd', '0'),
        ('logistics', 'supply_chain_efficiency', '0'),
        ('logistics', 'supply_disruption_risk', '0'),
        ('logistics', 'updated_at', 'CURRENT_TIMESTAMP'),
        ('products', 'created_at', 'CURRENT_TIMESTAMP'),
        ('products', 'updated_at', 'CURRENT_TIMESTAMP'),
        ('sales', 'created_at', 'CURRENT_TIMESTAMP'),
        ('sales', 'daily_demand', '0'),
        ('sales', 'demand_forecast', '0'),
        ('sales', 'monthly_demand', '0'),
        ('sales', 'predicted_reorder_quantity', '0'),
        ('sales', 'profit_usd', '0'),
        ('sales', 'revenue_usd', '0'),
        ('sales', 'seasonal_demand_index', '0'),
        ('sales', 'units_sold', '0'),
        ('suppliers', 'created_at', 'CURRENT_TIMESTAMP'),
        ('suppliers', 'updated_at', 'CURRENT_TIMESTAMP'),
        ('supply_chain_metrics', 'created_at', 'CURRENT_TIMESTAMP'),
        ('warehouses', 'created_at', 'CURRENT_TIMESTAMP'),
        ('warehouses', 'updated_at', 'CURRENT_TIMESTAMP')
    ) AS defaults_to_apply(table_name, column_name, default_sql)
    LOOP
        SELECT pg_get_expr(d.adbin, d.adrelid) INTO current_default
        FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE a.attrelid=format('public.%I', spec.table_name)::regclass
          AND a.attname=spec.column_name AND NOT a.attisdropped;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Missing column %.%', spec.table_name, spec.column_name;
        END IF;
        IF current_default IS DISTINCT FROM spec.default_sql THEN
            EXECUTE format('ALTER TABLE public.%I ALTER COLUMN %I SET DEFAULT %s',
                           spec.table_name, spec.column_name, spec.default_sql);
        END IF;
    END LOOP;
END;
$integrity_defaults$;

DO $integrity_not_null$
DECLARE
    spec RECORD;
    already_required BOOLEAN;
BEGIN
    FOR spec IN SELECT * FROM (VALUES
        ('inventory', 'product_id'),
        ('inventory', 'warehouse_id'),
        ('logistics', 'product_id'),
        ('logistics', 'supplier_id'),
        ('logistics', 'warehouse_id'),
        ('sales', 'product_id'),
        ('supply_chain_metrics', 'product_id')
    ) AS required_columns(table_name, column_name)
    LOOP
        SELECT a.attnotnull INTO already_required
        FROM pg_attribute a
        WHERE a.attrelid=format('public.%I', spec.table_name)::regclass
          AND a.attname=spec.column_name AND NOT a.attisdropped;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Missing column %.%', spec.table_name, spec.column_name;
        END IF;
        IF NOT already_required THEN
            EXECUTE format('ALTER TABLE public.%I ALTER COLUMN %I SET NOT NULL',
                           spec.table_name, spec.column_name);
        END IF;
    END LOOP;
END;
$integrity_not_null$;

DO $integrity_constraints$
DECLARE
    spec RECORD;
    existing_kind "char";
    already_validated BOOLEAN;
BEGIN
    FOR spec IN SELECT * FROM (VALUES
        ('agent_action_proposals', 'agent_action_proposals_action_check', 'c', 'CHECK ( action IN ( ''replenish'' , ''transfer'' , ''suspend_reorder'' , ''promotion'' , ''supplier_return'' ) )'),
        ('agent_action_proposals', 'agent_action_proposals_status_check', 'c', 'CHECK ( status IN ( ''pending_approval'' , ''approved'' , ''executed'' , ''rejected'' , ''obsolete'' ) )'),
        ('inventory', 'inventory_current_stock_check', 'c', 'CHECK ( current_stock >= 0 )'),
        ('inventory', 'inventory_inventory_optimization_score_check', 'c', 'CHECK ( inventory_optimization_score >= 0 AND inventory_optimization_score <= 100 )'),
        ('inventory', 'inventory_inventory_turnover_check', 'c', 'CHECK ( inventory_turnover >= 0 )'),
        ('inventory', 'inventory_operational_risk_score_check', 'c', 'CHECK ( operational_risk_score >= 0 AND operational_risk_score <= 100 )'),
        ('inventory', 'inventory_overstock_risk_check', 'c', 'CHECK ( overstock_risk >= 0 AND overstock_risk <= 100 )'),
        ('inventory', 'inventory_product_id_warehouse_id_key', 'u', 'UNIQUE ( product_id , warehouse_id )'),
        ('inventory', 'inventory_reorder_level_check', 'c', 'CHECK ( reorder_level >= 0 )'),
        ('inventory', 'inventory_safety_stock_check', 'c', 'CHECK ( safety_stock >= 0 )'),
        ('inventory', 'inventory_stockout_risk_check', 'c', 'CHECK ( stockout_risk >= 0 AND stockout_risk <= 100 )'),
        ('logistics', 'logistics_delivery_time_days_check', 'c', 'CHECK ( delivery_time_days >= 0 )'),
        ('logistics', 'logistics_on_time_delivery_rate_check', 'c', 'CHECK ( on_time_delivery_rate >= 0 AND on_time_delivery_rate <= 100 )'),
        ('logistics', 'logistics_product_id_supplier_id_warehouse_id_key', 'u', 'UNIQUE ( product_id , supplier_id , warehouse_id )'),
        ('logistics', 'logistics_shipping_cost_usd_check', 'c', 'CHECK ( shipping_cost_usd >= 0 )'),
        ('logistics', 'logistics_supply_chain_efficiency_check', 'c', 'CHECK ( supply_chain_efficiency >= 0 AND supply_chain_efficiency <= 100 )'),
        ('logistics', 'logistics_supply_disruption_risk_check', 'c', 'CHECK ( supply_disruption_risk >= 0 AND supply_disruption_risk <= 100 )'),
        ('products', 'products_product_cost_usd_check', 'c', 'CHECK ( product_cost_usd >= 0 )'),
        ('products', 'products_selling_price_usd_check', 'c', 'CHECK ( selling_price_usd >= 0 )'),
        ('sales', 'sales_daily_demand_check', 'c', 'CHECK ( daily_demand >= 0 )'),
        ('sales', 'sales_demand_forecast_check', 'c', 'CHECK ( demand_forecast >= 0 )'),
        ('sales', 'sales_month_check', 'c', 'CHECK ( month BETWEEN 1 AND 12 )'),
        ('sales', 'sales_monthly_demand_check', 'c', 'CHECK ( monthly_demand >= 0 )'),
        ('sales', 'sales_predicted_reorder_quantity_check', 'c', 'CHECK ( predicted_reorder_quantity >= 0 )'),
        ('sales', 'sales_quarter_check', 'c', 'CHECK ( quarter BETWEEN 1 AND 4 )'),
        ('sales', 'sales_revenue_usd_check', 'c', 'CHECK ( revenue_usd >= 0 )'),
        ('sales', 'sales_units_sold_check', 'c', 'CHECK ( units_sold >= 0 )'),
        ('sales', 'sales_year_check', 'c', 'CHECK ( year >= 2000 )'),
        ('suppliers', 'suppliers_lead_time_days_check', 'c', 'CHECK ( lead_time_days >= 0 )'),
        ('suppliers', 'suppliers_supplier_performance_score_check', 'c', 'CHECK ( supplier_performance_score >= 0 AND supplier_performance_score <= 100 )'),
        ('suppliers', 'suppliers_supplier_rating_check', 'c', 'CHECK ( supplier_rating >= 0 AND supplier_rating <= 5 )'),
        ('suppliers', 'suppliers_sustainability_score_check', 'c', 'CHECK ( sustainability_score >= 0 AND sustainability_score <= 100 )'),
        ('supply_chain_metrics', 'supply_chain_metrics_inventory_optimization_score_check', 'c', 'CHECK ( inventory_optimization_score >= 0 AND inventory_optimization_score <= 100 )'),
        ('supply_chain_metrics', 'supply_chain_metrics_operational_risk_score_check', 'c', 'CHECK ( operational_risk_score >= 0 AND operational_risk_score <= 100 )'),
        ('supply_chain_metrics', 'supply_chain_metrics_supplier_performance_score_check', 'c', 'CHECK ( supplier_performance_score >= 0 AND supplier_performance_score <= 100 )'),
        ('supply_chain_metrics', 'supply_chain_metrics_supply_chain_efficiency_check', 'c', 'CHECK ( supply_chain_efficiency >= 0 AND supply_chain_efficiency <= 100 )'),
        ('supply_chain_metrics', 'supply_chain_metrics_sustainability_score_check', 'c', 'CHECK ( sustainability_score >= 0 AND sustainability_score <= 100 )'),
        ('warehouses', 'warehouses_storage_capacity_check', 'c', 'CHECK ( storage_capacity >= 0 )'),
        ('warehouses', 'warehouses_utilization_rate_check', 'c', 'CHECK ( utilization_rate >= 0 AND utilization_rate <= 100 )')
    ) AS required_constraints(table_name, constraint_name, constraint_kind, constraint_sql)
    LOOP
        SELECT c.contype, c.convalidated INTO existing_kind, already_validated
        FROM pg_constraint c
        WHERE c.conrelid=format('public.%I', spec.table_name)::regclass
          AND c.conname=spec.constraint_name;
        IF NOT FOUND THEN
            EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I %s%s',
                           spec.table_name, spec.constraint_name, spec.constraint_sql,
                           CASE WHEN spec.constraint_kind='c' THEN ' NOT VALID' ELSE '' END);
            already_validated := spec.constraint_kind <> 'c';
        ELSIF existing_kind::text <> spec.constraint_kind THEN
            RAISE EXCEPTION 'Unexpected type for constraint %.%', spec.table_name, spec.constraint_name;
        END IF;
        IF NOT already_validated THEN
            EXECUTE format('ALTER TABLE public.%I VALIDATE CONSTRAINT %I',
                           spec.table_name, spec.constraint_name);
        END IF;
    END LOOP;
END;
$integrity_constraints$;
-- END EXISTING TABLE INTEGRITY MIGRATION

-- END JUPITER SCHEMA
COMMIT;
