-- Requires the administrative preparation 05-migration-permissions.sql first.
-- app and migrator share ownership rights; existing and future public objects
-- created by either login must use migrator as their effective owner.
DO $shared_owner$
BEGIN
    IF NOT pg_has_role('app', current_user, 'USAGE') THEN
        RAISE EXCEPTION 'Shared owner access is not prepared. Execute infra/sql/05-migration-permissions.sql as dbadmin, then reconnect app and retry Deploy AWS';
    END IF;
    IF NOT EXISTS (
        SELECT FROM pg_db_role_setting s
        WHERE s.setrole='app'::regrole
          AND s.setdatabase=(SELECT oid FROM pg_database WHERE datname=current_database())
          AND ('role=' || current_user)=ANY(s.setconfig)
    ) THEN
        RAISE EXCEPTION 'app login must use the migration owner. Execute infra/sql/05-migration-permissions.sql as dbadmin and reconnect app';
    END IF;
END;
$shared_owner$;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO app;
