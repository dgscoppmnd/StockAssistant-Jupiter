import logging
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any

from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from DataBaseManagement.dbConectionPostgres import db_context

logger = logging.getLogger("api.db")

# IS done: Funciones para el manejo de los registros de la tabla "tasks": 
# insert_record, get_record_by_id, get_all_records, 
# delete_record, get_expired_tasks, count_overdue_tasks y update_record. 
# Estas funciones deben utilizar consultas SQL parametrizadas para evitar 
# inyecciones SQL y deben manejar adecuadamente las conexiones a la base
# de datos utilizando el contexto proporcionado por get_db().
def insert_record_Generic(table: str, data: dict[str, Any], connection: Any = None) -> dict[str, Any]:
    if not data:
        raise ValueError("El cuerpo 'data' no puede estar vacio.")

    columns = list(data.keys())
    values = [data[column] for column in columns]

    query = sql.SQL(
        "INSERT INTO {table} ({fields}) VALUES ({placeholders}) RETURNING *"
    ).format(
        table=sql.Identifier(table),
        fields=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, values)
            created_row = cursor.fetchone()
        connection.commit()

    logger.info("event=db_insert table=%s created=%s", table, bool(created_row))

    return dict(created_row) if created_row else {}

# Actualiza un registro en la tabla especificada por el id_column (por defecto "id") 
# con los datos proporcionados en el diccionario data.
# id_column se utiliza para identificar el registro a actualizar. 
# La función devuelve el registro actualizado como un diccionario o None si no se encontró ningún registro con el id especificado. Si el cuerpo data está vacío, se lanza un ValueError. 
def update_record_Generic(table: str, record_id: Any, data: dict[str, Any], id_column: str = "id", connection: Any = None) -> dict[str, Any] | None:
    if record_id is None:
        raise ValueError("El campo 'id' es obligatorio.")

    if not data:
        raise ValueError("El cuerpo 'data' no puede estar vacio.")

    assignments = [
        sql.SQL("{field} = {placeholder}").format(
            field=sql.Identifier(column),
            placeholder=sql.Placeholder(),
        )
        for column in data.keys()
    ]

    query = sql.SQL(
        "UPDATE {table} SET {assignments} WHERE {id_column} = {id_placeholder} RETURNING *"
    ).format(
        table=sql.Identifier(table),
        assignments=sql.SQL(", ").join(assignments),
        id_column=sql.Identifier(id_column),
        id_placeholder=sql.Placeholder(),
    )

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, [*data.values(), record_id])
            updated_row = cursor.fetchone()
        connection.commit()

    logger.info("event=db_update table=%s id_column=%s updated=%s", table, id_column, bool(updated_row))

    return dict(updated_row) if updated_row else None

def delete_record_Generic(table: str, record_id: Any, id_column: str = "id", connection: Any = None) -> bool:
    query = sql.SQL("DELETE FROM {table} WHERE {id_column} = %s RETURNING {id_column}").format(
        table=sql.Identifier(table),
        id_column=sql.Identifier(id_column),
    )

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, [record_id])
            deleted_row = cursor.fetchone()
        connection.commit()

    logger.info("event=db_delete table=%s id_column=%s deleted_row=%s", table, id_column, bool(deleted_row))

    return bool(deleted_row)

def get_record_by_id_Generic(table: str, record_id: Any, id_column: str = "id", connection: Any = None) -> dict[str, Any] | None:
    query = sql.SQL("SELECT * FROM {table} WHERE {id_column} = %s").format(
        table=sql.Identifier(table),
        id_column=sql.Identifier(id_column),
    )

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, [record_id])
            row = cursor.fetchone()

    logger.info("event=db_get_by_id table=%s id_column=%s found=%s", table, id_column, bool(row))

    return dict(row) if row else None

def get_all_records_Generic(table: str, connection: Any = None) -> list[dict[str, Any]]:
    query = sql.SQL("SELECT * FROM {table}").format(table=sql.Identifier(table))

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    logger.info("event=db_get_all table=%s count=%s", table, len(rows))

    return [dict(row) for row in rows]

def get_rows_by_condition_Generic(table: str, condition: str, params: list[Any], connection: Any = None) -> list[dict[str, Any]]:
    query = sql.SQL("SELECT * FROM {table} WHERE {condition}").format(
        table=sql.Identifier(table),
        condition=sql.SQL(condition),
    )

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    logger.info("event=db_get_by_condition table=%s condition=%s count=%s", table, condition, len(rows))

    return [dict(row) for row in rows]

def get_rows_by_field_value_Generic(table: str, field: str, value: Any, connection: Any = None) -> list[dict[str, Any]]:
    query = sql.SQL("SELECT * FROM {table} WHERE {field} = %s").format(
        table=sql.Identifier(table),
        field=sql.Identifier(field),
    )

    with nullcontext(connection) if connection is not None else db_context() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, [value])
            rows = cursor.fetchall()

    logger.info("event=db_get_by_field_value table=%s field=%s value=%s count=%s", table, field, value, len(rows))

    return [dict(row) for row in rows]

def count_rows_by_condition_Generic(table: str, condition: str, params: list[Any], connection: Any = None) -> int:
    query = sql.SQL("SELECT COUNT(*) FROM {table} WHERE {condition}").format(
        table=sql.Identifier(table),
        condition=sql.SQL(condition),
    )

    with nullcontext(connection) if connection is not None else get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            count = cursor.fetchone()[0]

    logger.info("event=db_count_by_condition table=%s condition=%s count=%s", table, condition, count)

    return count

