-- Vista de LECTURA con la forma de public.productos sobre el dataset cargado en public.products.
-- Solo se usa en AWS (PRODUCTS_READ_RELATION=productos_catalogo). En local no se crea.
-- Ejecutar como migrator.
-- pk_product = parte numérica de product_id (PRD0000001 -> 1).

CREATE INDEX IF NOT EXISTS ix_products_pk_numeric
    ON public.products (((substring(product_id from '[0-9]+'))::bigint));

CREATE OR REPLACE VIEW public.productos_catalogo AS
SELECT
    (substring(p.product_id from '[0-9]+'))::bigint AS pk_product,
    p.product_id                                    AS cdgo_producto_externo,
    p.product_name                                  AS name_product,
    p.description                                   AS description_product,
    FALSE                                           AS disabled,
    p.selling_price_usd::numeric(18,4)              AS price,
    1                                               AS unit,
    p.selling_price_usd::numeric(18,4)              AS final_price,
    0::numeric(18,4)                                AS discount,
    NULL::timestamptz                               AS discount_end_date,
    1                                               AS fk_currency,
    'USD'::varchar(50)                              AS currency,
    0::numeric(10,2)                                AS user_rating,
    NULL::varchar(255)                              AS link,
    p.created_at::timestamptz                       AS creation_date,
    1::bigint                                       AS fk_last_update_user,
    p.updated_at::timestamptz                       AS last_update,
    p.brand::varchar(200)                           AS supplier
FROM public.products p;

GRANT SELECT ON public.productos_catalogo TO app;
