CREATE ROLE migrator LOGIN PASSWORD :'migpass' CONNECTION LIMIT 5;
CREATE ROLE app      LOGIN PASSWORD :'apppass' CONNECTION LIMIT 20;

-- Solo para una instalacion nueva. Para una base existente ejecutar como dbadmin
-- 05-migration-permissions.sql: instala extensiones, repara propietarios y concede
-- permisos sobre los objetos actuales sin recrear roles ni cambiar contrasenas.

REVOKE ALL ON DATABASE stockassistant FROM PUBLIC;
GRANT CONNECT ON DATABASE stockassistant TO migrator, app;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO migrator;
GRANT USAGE ON SCHEMA public TO app;

-- En RDS dbadmin no es superusuario: necesita ser miembro de migrator
-- temporalmente para cambiar sus privilegios por defecto.
GRANT migrator TO dbadmin;

-- Lo que cree migrator será accesible para app (DML, sin DDL)
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app;

REVOKE migrator FROM dbadmin;
