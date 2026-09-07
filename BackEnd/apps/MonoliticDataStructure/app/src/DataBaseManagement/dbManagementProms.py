from typing import Any
from DataBaseManagement.dbManagement import get_rows_by_condition_Generic, insert_record_Generic, update_record_Generic, delete_record_Generic, get_record_by_id_Generic, get_all_records_Generic,get_rows_by_field_value_Generic

def insert_prom_record(data: dict[str, Any]) -> dict[str, Any]:
    return insert_record_Generic(table="proms", data=data)

def update_prom_record(record_id: Any, data: dict[str, Any], id_column: str = "id") -> dict[str, Any] | None:
    return update_record_Generic(table="proms", record_id=record_id, data=data, id_column=id_column)

def delete_prom_record(record_id: Any, id_column: str = "id") -> dict[str, Any] | None:
    return delete_record_Generic(table="proms", record_id=record_id, id_column=id_column)       

def get_prom_record_by_id(record_id: Any, id_column: str = "id") -> dict[str, Any] | None:
    return get_record_by_id_Generic(table="proms", record_id=record_id, id_column=id_column)

def get_all_prom_records() -> list[dict[str, Any]]:
    return get_all_records_Generic(table="proms")

def get_proms_by_condition(condition: str, params: list[Any]) -> list[dict[str, Any]]:
    return get_rows_by_condition_Generic(table="proms", condition=condition, params=params)

def get_proms_by_field_value(field: str, value: Any) -> list[dict[str, Any]]:
    return get_rows_by_field_value_Generic(table="proms", field=field, value=value)