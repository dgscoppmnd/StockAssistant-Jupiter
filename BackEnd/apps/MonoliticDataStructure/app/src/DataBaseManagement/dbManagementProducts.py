import logging
from typing import Any

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
	return get_all_records_Generic(table=TableNameProducts, connection=connection)


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
