import logging
from contextlib import nullcontext
from typing import Any
from psycopg2.extras import RealDictCursor
from DataBaseManagement.dbConectionPostgres import db_context

from DataBaseManagement.dbManagement import (
	count_rows_by_condition_Generic,
	delete_record_Generic,
	get_all_records_Generic,
	get_record_by_id_Generic,
	get_rows_by_condition_Generic,
	insert_record_Generic,
	update_record_Generic,
)

logger = logging.getLogger("api.dbProducts")

TableNameProducts = "productos"


def insert_product(data: dict[str, Any], connection: Any = None) -> dict[str, Any]:
	return insert_record_Generic(table=TableNameProducts, data=data, connection=connection)


def update_product(
	record_id: Any,
	data: dict[str, Any],
	id_column: str = "pk_product",
	connection: Any = None,
) -> dict[str, Any] | None:
	return update_record_Generic(
		table=TableNameProducts,
		record_id=record_id,
		data=data,
		id_column=id_column,
		connection=connection,
	)


def delete_product(record_id: Any, id_column: str = "pk_product", connection: Any = None) -> bool:
	return delete_record_Generic(table=TableNameProducts, record_id=record_id, id_column=id_column, connection=connection)


def get_product_by_id(
	record_id: Any,
	id_column: str = "pk_product",
	connection: Any = None,
) -> dict[str, Any] | None:
	return get_record_by_id_Generic(table=TableNameProducts, record_id=record_id, id_column=id_column, connection=connection)


def get_all_products(connection: Any = None) -> list[dict[str, Any]]:
	with nullcontext(connection) if connection is not None else db_context() as conn:
		with conn.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute("""
				SELECT p.*, image.public_url AS default_image_url
				FROM public.productos p
				LEFT JOIN public.products_images image ON image.product_id = p.pk_product AND image.is_default = TRUE
				ORDER BY p.pk_product ASC
			""")
			return [dict(row) for row in cursor.fetchall()]


def get_products_page(page: int, page_size: int, connection: Any = None) -> dict[str, Any]:
	if page < 1 or not 1 <= page_size <= 100:
		raise ValueError("Página o tamaño de página fuera del rango permitido.")
	with nullcontext(connection) if connection is not None else db_context() as conn:
		with conn.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute("SELECT COUNT(*) AS total FROM public.productos")
			total = cursor.fetchone()["total"]
			# Si se elimina la última fila de la última página, devolver la anterior.
			page = min(page, max(1, (total + page_size - 1) // page_size))
			cursor.execute("""
				SELECT p.*, image.public_url AS default_image_url
				FROM (
					SELECT * FROM public.productos ORDER BY pk_product ASC LIMIT %s OFFSET %s
				) p
				LEFT JOIN public.products_images image ON image.product_id = p.pk_product AND image.is_default = TRUE
				ORDER BY p.pk_product ASC
			""", (page_size, (page - 1) * page_size))
			return {"items": [dict(row) for row in cursor.fetchall()], "total": total, "page": page, "page_size": page_size}


def get_disabled_products(connection: Any = None) -> list[dict[str, Any]]:
	query = """
		disabled = TRUE
		ORDER BY pk_product ASC
	"""
	return get_rows_by_condition_Generic(table=TableNameProducts, condition=query, params=[], connection=connection)


def count_disabled_products(connection: Any = None) -> int:
	query = """
		disabled = TRUE
	"""
	return count_rows_by_condition_Generic(table=TableNameProducts, condition=query, params=[], connection=connection)
