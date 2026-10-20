-- Run AFTER the canonical init.sql as migrator. No numeric-ID extraction.
-- Old Lambda deployments may keep this read alias until their configuration is refreshed.
CREATE OR REPLACE VIEW public.productos_catalogo AS SELECT * FROM public.productos;
GRANT SELECT ON public.productos_catalogo TO app;
