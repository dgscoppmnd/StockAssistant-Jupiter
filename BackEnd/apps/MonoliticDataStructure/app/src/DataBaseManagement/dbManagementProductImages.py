import logging
from contextlib import nullcontext
from typing import Any

from psycopg2.extras import RealDictCursor

from DataBaseManagement.dbManagement import (
    delete_record_Generic,
    get_record_by_id_Generic,
    get_rows_by_condition_Generic,
    insert_record_Generic,
)

logger = logging.getLogger("api.dbproductimages")

TABLE_NAME_PRODUCT_IMAGES = "products_images"


def insert_product_image(data: dict[str, Any], connection: Any = None) -> dict[str, Any]:
    return insert_record_Generic(table=TABLE_NAME_PRODUCT_IMAGES, data=data, connection=connection)


def get_product_image_by_id(record_id: Any, id_column: str = "id", connection: Any = None) -> dict[str, Any] | None:
    return get_record_by_id_Generic(
        table=TABLE_NAME_PRODUCT_IMAGES,
        record_id=record_id,
        id_column=id_column,
        connection=connection,
    )


def get_product_images_by_product_id(product_id: int, connection: Any = None) -> list[dict[str, Any]]:
    query = """
        product_id = %s
        ORDER BY is_default DESC, created_at DESC, id DESC
    """
    return get_rows_by_condition_Generic(
        table=TABLE_NAME_PRODUCT_IMAGES,
        condition=query,
        params=[product_id],
        connection=connection,
    )


def get_default_product_image_by_product_id(product_id: int, connection: Any = None) -> dict[str, Any] | None:
    query = """
        product_id = %s AND is_default = TRUE
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """
    rows = get_rows_by_condition_Generic(
        table=TABLE_NAME_PRODUCT_IMAGES,
        condition=query,
        params=[product_id],
        connection=connection,
    )
    return rows[0] if rows else None


def set_default_product_image(image_id: int, product_id: int, connection: Any = None) -> dict[str, Any] | None:
    with nullcontext(connection) if connection is not None else nullcontext() as conn:
        if conn is None:
            raise ValueError("Se requiere una conexion valida para set_default_product_image")

        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM public.products_images
                WHERE id = %s AND product_id = %s
                """,
                [image_id, product_id],
            )
            selected = cursor.fetchone()
            if not selected:
                return None

            cursor.execute(
                """
                UPDATE public.products_images
                SET is_default = FALSE
                WHERE product_id = %s
                """,
                [product_id],
            )
            cursor.execute(
                """
                UPDATE public.products_images
                SET is_default = TRUE
                WHERE id = %s
                RETURNING *
                """,
                [image_id],
            )
            updated = cursor.fetchone()
        conn.commit()

    return dict(updated) if updated else None


def delete_product_image(record_id: Any, id_column: str = "id", connection: Any = None) -> bool:
    return delete_record_Generic(
        table=TABLE_NAME_PRODUCT_IMAGES,
        record_id=record_id,
        id_column=id_column,
        connection=connection,
    )
