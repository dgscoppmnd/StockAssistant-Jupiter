CREATE ROLE migrator LOGIN PASSWORD :'migpass' CONNECTION LIMIT 5;
CREATE ROLE app      LOGIN PASSWORD :'apppass' CONNECTION LIMIT 20;

-- Solo para una instalacion nueva. Para una base existente ejecutar como dbadmin
-- 05-migration-permissions.sql: instala extensiones, repara propietarios y concede
-- permisos sobre los objetos actuales sin recrear roles ni cambiar contrasenas.

REVOKE ALL ON DATABASE stockassistant FROM PUBLIC;
GRANT CONNECT ON DATABASE stockassistant TO migrator, app;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM app;
GRANT USAGE, CREATE ON SCHEMA public TO migrator;
GRANT USAGE ON SCHEMA public TO app;

-- En RDS dbadmin no es superusuario: necesita ser miembro de migrator
-- temporalmente para cambiar sus privilegios por defecto.
GRANT migrator TO dbadmin;

-- Privilegios operativos sobre objetos ya creados durante el bootstrap.
-- Los GRANT por defecto de abajo solo afectan a objetos futuros.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app;

-- Los historiales tecnicos no son datos editables por la aplicacion.
DO $protect_history$
DECLARE
    relation_name text;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY['schema_migrations', 'app_schema_updates', 'app_schema_update_history']
    LOOP
        IF to_regclass(format('public.%I', relation_name)) IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM app, PUBLIC', relation_name);
            IF relation_name <> 'schema_migrations' THEN
                EXECUTE format('GRANT SELECT ON TABLE public.%I TO app', relation_name);
            END IF;
        END IF;
    END LOOP;
END;
$protect_history$;

-- Privilegios directos para objetos futuros; el rol compartido al final
-- concede tambien la autoridad necesaria para modificar su estructura.
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO app;

REVOKE migrator FROM dbadmin;

-- Both logins may update data and structure through the same owner.
-- This intentionally also permits app to change the migration history objects.
-- New app connections create objects as migrator, so either login can ALTER
-- objects created by the other. Reconnect app sessions after applying this.
GRANT migrator TO app;
ALTER ROLE app IN DATABASE stockassistant SET role TO 'migrator';
