-- Repair an existing installation: execute as dbadmin in stockassistant.
-- Repeatable; no passwords, no role creation, no data changes.
-- All grants/ownership changes roll back together if any operation fails.
-- Only the application objects listed below and their sequences are managed.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '120s';
DO $repair_permissions$
DECLARE
    application_relations text[] := ARRAY[
        'agent_action_proposals', 'agent_decisions', 'app_schema_update_history',
        'app_schema_updates', 'automation_control', 'automation_events',
        'automation_rule_versions', 'automation_rules', 'automation_runs',
        'catalogues', 'catalogues_products', 'chat_conversations', 'chat_messages',
        'clients', 'clients_addresses', 'currency', 'error_log', 'external_data_cache',
        'globlal_addresses', 'goods_receipt_lines', 'goods_receipts', 'inventory',
        'inventory_currencies', 'inventory_exchange_rates', 'inventory_movements',
        'inventory_reservations', 'inventory_stock_levels', 'inventory_suppliers',
        'inventory_suppliers_addresses', 'inventory_transfer_lines', 'inventory_transfers',
        'inventory_unit_conversions', 'inventory_units', 'inventory_warehouses',
        'knowledge_chunks', 'knowledge_documents', 'knowledge_vector_deletions',
        'logistics', 'markets', 'markets_catalogues', 'product_inventory_config',
        'product_reviews', 'productos', 'productos_catalogo', 'products',
        'products_images', 'products_unified', 'proms', 'properties',
        'purchase_order_lines', 'purchase_orders', 'purchase_proposals', 'review_batches',
        'sales', 'sales_dispatch_lines', 'sales_dispatches', 'sales_document_events',
        'sales_invoice_lines', 'sales_invoices', 'sales_order_lines', 'sales_orders',
        'sales_return_lines', 'sales_returns', 'schema_migrations', 'suppliers',
        'supply_chain_metrics', 'type_catalog', 'type_client', 'type_funding_source',
        'ultimos_productos_creados', 'users', 'v_critical_stock',
        'v_product_performance', 'v_supplier_efficiency', 'warehouses'
    ];
    application_functions text[] := ARRAY[
        'public.update_updated_at_column()',
        'public.calculate_risk_score(integer,integer,integer,numeric)',
        'public.set_last_update_timestamp()',
        'public.invalidate_knowledge_index()',
        'public.retire_knowledge_vector()'
    ];
    relation_oids oid[];
    sequence_oids oid[];
    function_signature text;
    object record;
    temporary_membership boolean := false;
    previous_membership record;
    adjusted_membership boolean := false;
BEGIN
    IF current_database() <> 'stockassistant' THEN
        RAISE EXCEPTION 'Connect to stockassistant before repairing migration permissions';
    END IF;
    IF current_user IN ('app', 'migrator') THEN
        RAISE EXCEPTION 'Execute this preparation as dbadmin, not app or migrator';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'migrator')
       OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app') THEN
        RAISE EXCEPTION 'Roles migrator and app must already exist; run 01-roles.sql only for a new installation';
    END IF;
    IF NOT pg_try_advisory_xact_lock(702641903119) THEN
        RAISE EXCEPTION 'A schema update is running; retry this preparation afterwards';
    END IF;

    -- RDS administrators need membership of the target owner. Preserve any
    -- membership that predates this script; remove only the one added here.
    IF current_setting('server_version_num')::integer >= 160000 THEN
        -- PostgreSQL 16 separates membership from SET/INHERIT. A role creator
        -- can have ADMIN alone. Add/adjust only this administrator's own grant;
        -- preserve memberships issued by other grantors and restore options.
        IF NOT pg_has_role(current_user, 'migrator', 'USAGE')
           OR NOT pg_has_role(current_user, 'migrator', 'SET') THEN
            EXECUTE 'SELECT admin_option, inherit_option, set_option FROM pg_auth_members
                     WHERE roleid = ''migrator''::regrole AND member = $1::regrole
                       AND grantor = $1::regrole'
                INTO previous_membership USING current_user;
            temporary_membership := previous_membership.admin_option IS NULL;
            EXECUTE format('GRANT migrator TO %I WITH INHERIT TRUE, SET TRUE GRANTED BY %I',
                           current_user, current_user);
            adjusted_membership := true;
        END IF;
    ELSIF NOT pg_has_role(current_user, 'migrator', 'MEMBER') THEN
        EXECUTE format('GRANT migrator TO %I', current_user);
        temporary_membership := true;
    END IF;
    GRANT CONNECT ON DATABASE stockassistant TO migrator, app;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC, app;
    GRANT USAGE, CREATE ON SCHEMA public TO migrator;
    GRANT USAGE ON SCHEMA public TO app;

    -- Preinstall as administrator rather than granting database-wide CREATE
    -- or administrative role membership to the application/migration account.
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
    CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
    CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;

    SELECT coalesce(array_agg(c.oid), ARRAY[]::oid[]) INTO relation_oids
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = ANY(application_relations)
      AND c.relkind IN ('r', 'p', 'v', 'm')
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                      AND d.objid = c.oid AND d.deptype = 'e');

    -- Include both serial/identity sequences and sequences referenced by a
    -- column default, without touching unrelated sequences in public.
    SELECT coalesce(array_agg(c.oid), ARRAY[]::oid[]) INTO sequence_oids
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'S'
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                      AND d.objid = c.oid AND d.deptype = 'e')
      AND (EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                    AND d.objid = c.oid AND d.refclassid = 'pg_class'::regclass
                    AND d.refobjid = ANY(relation_oids) AND d.deptype IN ('a', 'i'))
           OR EXISTS (SELECT FROM pg_depend d JOIN pg_attrdef a ON a.oid = d.objid
                       WHERE d.classid = 'pg_attrdef'::regclass
                         AND d.refclassid = 'pg_class'::regclass AND d.refobjid = c.oid
                         AND a.adrelid = ANY(relation_oids)));

    FOR object IN
        SELECT c.oid, c.relname, c.relkind FROM pg_class c
        WHERE c.oid = ANY(relation_oids)
        ORDER BY c.relname
    LOOP
        EXECUTE format('ALTER %s public.%I OWNER TO migrator',
            CASE object.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                 ELSE 'TABLE' END, object.relname);
        IF object.relname = 'schema_migrations' THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM app, PUBLIC', object.relname);
        ELSIF object.relname IN ('app_schema_updates', 'app_schema_update_history') THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM app, PUBLIC', object.relname);
            EXECUTE format('GRANT SELECT ON TABLE public.%I TO app', object.relname);
        ELSE
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO app', object.relname);
        END IF;
    END LOOP;

    FOR object IN SELECT c.relname, c.relowner FROM pg_class c WHERE c.oid = ANY(sequence_oids)
    LOOP
        -- Owned sequences follow ALTER TABLE OWNER automatically; PostgreSQL
        -- does not allow assigning their owner independently of the table.
        IF object.relowner <> 'migrator'::regrole THEN
            EXECUTE format('ALTER SEQUENCE public.%I OWNER TO migrator', object.relname);
        END IF;
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE public.%I TO app', object.relname);
    END LOOP;

    FOREACH function_signature IN ARRAY application_functions
    LOOP
        FOR object IN SELECT p.oid::regprocedure AS signature FROM pg_proc p
            WHERE p.oid = to_regprocedure(function_signature)
              AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass
                              AND d.objid = p.oid AND d.deptype = 'e')
        LOOP
            EXECUTE format('ALTER FUNCTION %s OWNER TO migrator', object.signature);
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO app', object.signature);
        END LOOP;
    END LOOP;

    ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
    ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO app;
    ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
        GRANT EXECUTE ON FUNCTIONS TO app;

    IF adjusted_membership THEN
        IF temporary_membership THEN
            EXECUTE format('REVOKE migrator FROM %I GRANTED BY %I', current_user, current_user);
        ELSE
            EXECUTE format('GRANT migrator TO %I WITH ADMIN %s, INHERIT %s, SET %s GRANTED BY %I',
                           current_user,
                           CASE WHEN previous_membership.admin_option THEN 'TRUE' ELSE 'FALSE' END,
                           CASE WHEN previous_membership.inherit_option THEN 'TRUE' ELSE 'FALSE' END,
                           CASE WHEN previous_membership.set_option THEN 'TRUE' ELSE 'FALSE' END, current_user);
        END IF;
    ELSIF temporary_membership THEN
        EXECUTE format('REVOKE migrator FROM %I', current_user);
    END IF;
END;
$repair_permissions$;
COMMIT;
