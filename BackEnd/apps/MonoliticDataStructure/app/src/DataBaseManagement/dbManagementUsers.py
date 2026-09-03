import logging
from datetime import datetime, timezone
from typing import Any
from DataBaseManagement.dbManagement import get_rows_by_condition_Generic,insert_record_Generic, update_record_Generic, delete_record_Generic, get_record_by_id_Generic, get_all_records_Generic,get_rows_by_field_value_Generic, count_rows_by_condition_Generic

logger = logging.getLogger("api.dbUsers")

TableNameUsers = "users"
# IS done: Funciones para el manejo de los registros de la tabla "Users": 
# insert_record, get_record_by_id, get_all_records, 
# delete_record, get_expired_Users, count_overdue_Users y update_record. 
# Estas funciones deben utilizar consultas SQL parametrizadas para evitar 
# inyecciones SQL y deben manejar adecuadamente las conexiones a la base
# de datos utilizando el contexto proporcionado por get_db().
def insert_user(data: dict[str, Any], connection: Any = None) -> dict[str, Any]:
    return insert_record_Generic(table=TableNameUsers, data=data, connection=connection)
    
# Actualiza un registro en la tabla especificada por el id_column (por defecto "id") 
# con los datos proporcionados en el diccionario data.
# id_column se utiliza para identificar el registro a actualizar. 
# La función devuelve el registro actualizado como un diccionario o None si no se encontró ningún registro con el id especificado. Si el cuerpo data está vacío, se lanza un ValueError. 
def update_user(record_id: Any, data: dict[str, Any], id_column: str = "id", connection: Any = None) -> dict[str, Any] | None:
    return update_record_Generic(table=TableNameUsers, record_id=record_id, data=data, id_column=id_column, connection=connection)

def delete_user(record_id: Any, id_column: str = "id", connection: Any = None) -> bool:
    return delete_record_Generic(table=TableNameUsers, record_id=record_id, id_column=id_column, connection=connection)

def get_user_by_id(record_id: Any, id_column: str = "id", connection: Any = None) -> dict[str, Any] | None:
    return get_record_by_id_Generic(table=TableNameUsers, record_id=record_id, id_column=id_column, connection=connection)

def get_user_by_email(email: str, connection: Any = None) -> dict[str, Any] | None:
    query = "LOWER(email) = LOWER(%s)"
    rows = get_rows_by_condition_Generic(table=TableNameUsers, condition=query, params=[email], connection=connection)
    return rows[0] if rows else None

def get_user_by_google_sub(google_sub: str, connection: Any = None) -> dict[str, Any] | None:
    rows = get_rows_by_field_value_Generic(table=TableNameUsers, field="google_sub", value=google_sub, connection=connection)
    return rows[0] if rows else None

def get_all_users(connection: Any = None) -> list[dict[str, Any]]:
    return get_all_records_Generic(table=TableNameUsers, connection=connection)

def get_expired_users(connection: Any = None) -> list[dict[str, Any]]:
    query = """
        deadline IS NOT NULL
        AND deadline < %s
        ORDER BY deadline ASC
    """
    return get_rows_by_condition_Generic(table=TableNameUsers, condition=query, params=[datetime.now(timezone.utc)], connection=connection)

def count_overdue_users(connection: Any = None) -> int:
    query = """
         deadline IS NOT NULL
        AND deadline < %s
    """
    return count_rows_by_condition_Generic(table=TableNameUsers, condition=query, params=[datetime.now(timezone.utc)], connection=connection)   
