-- Ejecutar como migrator (el rol app solo recibe DML por los privilegios por defecto).
CREATE TABLE IF NOT EXISTS public.login_attempts (
    key          text PRIMARY KEY,
    failures     integer     NOT NULL DEFAULT 0,
    window_start timestamptz NOT NULL DEFAULT now(),
    locked_until timestamptz
);
