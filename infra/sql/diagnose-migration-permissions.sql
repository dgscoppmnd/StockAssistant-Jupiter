-- Read-only: run in stockassistant as dbadmin or migrator (e.g. pgAdmin).
-- Does not print credentials or application data, nor change ownership/grants.
BEGIN READ ONLY;

SELECT current_database() AS database_name, session_user, current_user,
       has_database_privilege('migrator', current_database(), 'CONNECT') AS migrator_connect,
       has_database_privilege('migrator', current_database(), 'CREATE') AS migrator_database_create,
       has_schema_privilege('migrator', 'public', 'USAGE') AS migrator_schema_usage,
       has_schema_privilege('migrator', 'public', 'CREATE') AS migrator_schema_create;

-- Missing extensions should be installed once by dbadmin before migration.
SELECT required.name, installed.extversion AS installed_version,
       pg_get_userbyid(installed.extowner) AS extension_owner
FROM (VALUES ('uuid-ossp'), ('pgcrypto'), ('pg_trgm')) AS required(name)
LEFT JOIN pg_extension installed ON installed.extname = required.name
ORDER BY required.name;

-- Owning-role privileges are needed for ALTER/DROP, not just DML grants.
-- Extension-owned objects are excluded: do not reassign their ownership.
SELECT n.nspname AS schema_name, c.relname AS object_name, c.relkind AS kind,
       pg_get_userbyid(c.relowner) AS owner,
       pg_has_role('migrator', c.relowner, 'USAGE') AS migrator_has_owner_privileges
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
  AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                  AND d.objid = c.oid AND d.deptype = 'e')
ORDER BY migrator_has_owner_privileges, c.relkind, c.relname;

SELECT n.nspname AS schema_name, p.proname AS routine_name,
       pg_get_function_identity_arguments(p.oid) AS arguments,
       pg_get_userbyid(p.proowner) AS owner,
       pg_has_role('migrator', p.proowner, 'USAGE') AS migrator_has_owner_privileges
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass
                  AND d.objid = p.oid AND d.deptype = 'e')
ORDER BY migrator_has_owner_privileges, p.proname, arguments;

COMMIT;
