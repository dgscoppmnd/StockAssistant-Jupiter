-- One-time preparation, connected to stockassistant as dbadmin.
-- Does not grant administrative roles to migrator or app.
-- RDS must allow these extensions for the installed PostgreSQL version.
BEGIN;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;
COMMIT;
