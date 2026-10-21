-- Restore runtime grants on existing application objects after 01-roles.sql.
-- Executed automatically by Deploy AWS as migrator, after the canonical schema.
-- Only the listed application objects are touched; owners and login roles stay unchanged.
-- Recovery: add a forward migration revoking a specific excess grant if required.
DO $runtime_permissions$
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
    object record;
    function_signature text;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app') THEN
        RAISE EXCEPTION 'Runtime role app is missing; prepare database roles before deploying';
    END IF;

    SELECT coalesce(array_agg(c.oid), ARRAY[]::oid[]) INTO relation_oids
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = ANY(application_relations)
      AND c.relkind IN ('r', 'p', 'v', 'm')
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                      AND d.objid = c.oid AND d.deptype = 'e');

    FOR object IN SELECT c.relname FROM pg_class c WHERE c.oid = ANY(relation_oids)
    LOOP
        IF object.relname = 'schema_migrations' THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM app, PUBLIC', object.relname);
        ELSIF object.relname IN ('app_schema_updates', 'app_schema_update_history') THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM app, PUBLIC', object.relname);
            EXECUTE format('GRANT SELECT ON TABLE public.%I TO app', object.relname);
        ELSE
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO app', object.relname);
        END IF;
    END LOOP;

    -- Include owned serial/identity sequences and sequences used by column defaults.
    FOR object IN
        SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'S'
          AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                          AND d.objid = c.oid AND d.deptype = 'e')
          AND (EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                        AND d.objid = c.oid AND d.refclassid = 'pg_class'::regclass
                        AND d.refobjid = ANY(relation_oids) AND d.deptype IN ('a', 'i'))
               OR EXISTS (SELECT FROM pg_depend d JOIN pg_attrdef a ON a.oid = d.objid
                           WHERE d.classid = 'pg_attrdef'::regclass
                             AND d.refclassid = 'pg_class'::regclass AND d.refobjid = c.oid
                             AND a.adrelid = ANY(relation_oids)))
    LOOP
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE public.%I TO app', object.relname);
    END LOOP;

    FOREACH function_signature IN ARRAY application_functions
    LOOP
        IF to_regprocedure(function_signature) IS NOT NULL THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO app', to_regprocedure(function_signature));
        END IF;
    END LOOP;
END;
$runtime_permissions$;

-- Future objects created by this migration owner must also be usable by app.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app;
