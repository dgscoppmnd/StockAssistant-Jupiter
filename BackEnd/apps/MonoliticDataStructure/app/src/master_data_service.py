from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


class MasterDataError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class MasterDefinition:
    table: str
    fields: tuple[str, ...]
    required: tuple[str, ...]
    numeric: tuple[str, ...] = ()
    decimal: tuple[str, ...] = ()
    boolean: tuple[str, ...] = ()
    nullable: tuple[str, ...] = ()


RESOURCES: dict[str, MasterDefinition] = {
    "units": MasterDefinition("public.inventory_units", ("code", "name", "description"), ("code", "name"), nullable=("description",)),
    "currencies": MasterDefinition("public.inventory_currencies", ("iso_code", "name", "symbol"), ("iso_code", "name"), nullable=("symbol",)),
    "warehouses": MasterDefinition("public.inventory_warehouses", ("code", "name", "description", "is_active"), ("code", "name"), boolean=("is_active",), nullable=("description",)),
    "suppliers": MasterDefinition("public.inventory_suppliers", ("supplier_code", "name", "email", "phone"), ("name",), nullable=("supplier_code", "email", "phone")),
    "unit-conversions": MasterDefinition("public.inventory_unit_conversions", ("product_id", "from_unit_id", "to_unit_id", "factor"), ("from_unit_id", "to_unit_id", "factor"), numeric=("product_id", "from_unit_id", "to_unit_id"), decimal=("factor",), nullable=("product_id",)),
    "knowledge-documents": MasterDefinition("public.knowledge_documents", ("title", "content", "source", "expires_at", "is_active"), ("title", "content", "source"), boolean=("is_active",), nullable=("expires_at",)),
}


class MasterDataService:
    def __init__(self, connection: Any):
        self.connection = connection

    def _definition(self, resource: str) -> MasterDefinition:
        definition = RESOURCES.get(resource)
        if not definition:
            raise MasterDataError("Recurso maestro no disponible", 404)
        return definition

    def _values(self, definition: MasterDefinition, values: dict[str, Any], creating: bool) -> dict[str, Any]:
        unknown = set(values) - set(definition.fields)
        if unknown:
            raise MasterDataError(f"Campos no permitidos: {', '.join(sorted(unknown))}")
        cleaned: dict[str, Any] = {}
        for field, value in values.items():
            if isinstance(value, str):
                value = value.strip()
            if field in definition.nullable and value == "":
                value = None
            if field in definition.numeric and value is not None:
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise MasterDataError(f"{field} debe ser un entero") from exc
            if field in definition.decimal and value is not None:
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, ValueError) as exc:
                    raise MasterDataError(f"{field} debe ser decimal") from exc
                if value <= 0:
                    raise MasterDataError(f"{field} debe ser mayor que cero")
            if field in definition.boolean and value is not None:
                if not isinstance(value, bool):
                    raise MasterDataError(f"{field} debe ser booleano")
            cleaned[field] = value
        if creating:
            missing = [field for field in definition.required if not cleaned.get(field)]
            if missing:
                raise MasterDataError(f"Campos obligatorios: {', '.join(missing)}")
            for field in definition.boolean:
                cleaned.setdefault(field, True)
        if not cleaned:
            raise MasterDataError("No hay cambios para guardar")
        return cleaned

    def list(self, resource: str) -> list[dict[str, Any]]:
        definition = self._definition(resource)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(f"SELECT id, {', '.join(definition.fields)}, created_at" + (", updated_at" if resource != "unit-conversions" else "") + f" FROM {definition.table} ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def create(self, resource: str, values: dict[str, Any]) -> dict[str, Any]:
        definition = self._definition(resource)
        data = self._values(definition, values, creating=True)
        columns = list(data)
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"INSERT INTO {definition.table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))}) RETURNING id", tuple(data[column] for column in columns))
                row_id = int(cursor.fetchone()["id"])
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se pudo crear: existe un valor duplicado o una referencia no valida", 409) from exc
        return self.get(resource, row_id)

    def get(self, resource: str, record_id: int) -> dict[str, Any]:
        definition = self._definition(resource)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(f"SELECT id, {', '.join(definition.fields)}, created_at" + (", updated_at" if resource != "unit-conversions" else "") + f" FROM {definition.table} WHERE id = %s", (record_id,))
            row = cursor.fetchone()
        if not row:
            raise MasterDataError("Registro maestro no encontrado", 404)
        return dict(row)

    def update(self, resource: str, record_id: int, values: dict[str, Any]) -> dict[str, Any]:
        definition = self._definition(resource)
        data = self._values(definition, values, creating=False)
        assignments = [f"{field} = %s" for field in data]
        if resource != "unit-conversions":
            assignments.append("updated_at = CURRENT_TIMESTAMP")
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"UPDATE {definition.table} SET {', '.join(assignments)} WHERE id = %s", (*data.values(), record_id))
                if cursor.rowcount == 0:
                    raise MasterDataError("Registro maestro no encontrado", 404)
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se pudo actualizar: existe un valor duplicado o una referencia no valida", 409) from exc
        return self.get(resource, record_id)

    def delete(self, resource: str, record_id: int) -> None:
        definition = self._definition(resource)
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {definition.table} WHERE id = %s", (record_id,))
                if cursor.rowcount == 0:
                    raise MasterDataError("Registro maestro no encontrado", 404)
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se puede eliminar porque el registro tiene dependencias", 409) from exc
