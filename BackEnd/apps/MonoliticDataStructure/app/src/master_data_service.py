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
    id_column: str = "id"
    created_column: str | None = "created_at"
    updated_column: str | None = "updated_at"
    numeric: tuple[str, ...] = ()
    decimal: tuple[str, ...] = ()
    boolean: tuple[str, ...] = ()
    nullable: tuple[str, ...] = ()


RESOURCES: dict[str, MasterDefinition] = {
    "units": MasterDefinition("public.inventory_units", ("code", "name", "description"), ("code", "name"), nullable=("description",)),
    "currencies": MasterDefinition("public.inventory_currencies", ("iso_code", "name", "symbol"), ("iso_code", "name"), nullable=("symbol",)),
    "warehouses": MasterDefinition("public.inventory_warehouses", ("code", "name", "description", "is_active"), ("code", "name"), boolean=("is_active",), nullable=("description",)),
    "suppliers": MasterDefinition("public.inventory_suppliers", ("supplier_code", "name", "email", "phone"), ("name",), nullable=("supplier_code", "email", "phone")),
    "unit-conversions": MasterDefinition("public.inventory_unit_conversions", ("product_id", "from_unit_id", "to_unit_id", "factor"), ("from_unit_id", "to_unit_id", "factor"), updated_column=None, numeric=("product_id", "from_unit_id", "to_unit_id"), decimal=("factor",), nullable=("product_id",)),
    "knowledge-documents": MasterDefinition("public.knowledge_documents", ("title", "content", "source", "expires_at", "is_active"), ("title", "content", "source"), boolean=("is_active",), nullable=("expires_at",)),
    "client-types": MasterDefinition("public.type_client", ("name",), ("name",), id_column="pk_type_client", created_column=None, updated_column=None),
    "clients": MasterDefinition("public.clients", ("client_code", "name", "description", "fk_type_client"), ("name", "fk_type_client"), id_column="pk_client", created_column="creation_date", updated_column="last_update", numeric=("fk_type_client",), nullable=("client_code", "description")),
    "global-addresses": MasterDefinition("public.globlal_addresses", ("address_line_1", "address_line_2", "city", "state_province", "postal_code", "country_code", "country_name", "contact_name", "contact_phone", "contact_email", "notes"), ("address_line_1", "city", "country_code"), nullable=("address_line_2", "state_province", "postal_code", "country_name", "contact_name", "contact_phone", "contact_email", "notes")),
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
        timestamps = ([f"{definition.created_column} AS created_at"] if definition.created_column else []) + ([f"{definition.updated_column} AS updated_at"] if definition.updated_column else [])
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            if resource == "clients":
                cursor.execute(f"SELECT {definition.id_column} AS id, {', '.join(definition.fields + tuple(timestamps))}, EXISTS (SELECT 1 FROM public.clients_addresses ca WHERE ca.client_id = public.clients.pk_client) AS is_in_use FROM {definition.table} ORDER BY {definition.id_column} DESC")
                return [dict(row) for row in cursor.fetchall()]
            if resource == "suppliers":
                cursor.execute(f"SELECT {definition.id_column} AS id, {', '.join(definition.fields + tuple(timestamps))}, EXISTS (SELECT 1 FROM public.inventory_suppliers_addresses sa WHERE sa.supplier_id = public.inventory_suppliers.id) AS is_in_use FROM {definition.table} ORDER BY {definition.id_column} DESC")
                return [dict(row) for row in cursor.fetchall()]
            cursor.execute(f"SELECT {definition.id_column} AS id, {', '.join(definition.fields + tuple(timestamps))} FROM {definition.table} ORDER BY {definition.id_column} DESC")
            return [dict(row) for row in cursor.fetchall()]

    def create(self, resource: str, values: dict[str, Any]) -> dict[str, Any]:
        definition = self._definition(resource)
        data = self._values(definition, values, creating=True)
        columns = list(data)
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"INSERT INTO {definition.table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))}) RETURNING {definition.id_column} AS id", tuple(data[column] for column in columns))
                row_id = int(cursor.fetchone()["id"])
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se pudo crear: existe un valor duplicado o una referencia no valida", 409) from exc
        return self.get(resource, row_id)

    def get(self, resource: str, record_id: int) -> dict[str, Any]:
        definition = self._definition(resource)
        timestamps = ([f"{definition.created_column} AS created_at"] if definition.created_column else []) + ([f"{definition.updated_column} AS updated_at"] if definition.updated_column else [])
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(f"SELECT {definition.id_column} AS id, {', '.join(definition.fields + tuple(timestamps))} FROM {definition.table} WHERE {definition.id_column} = %s", (record_id,))
            row = cursor.fetchone()
        if not row:
            raise MasterDataError("Registro maestro no encontrado", 404)
        return dict(row)

    def update(self, resource: str, record_id: int, values: dict[str, Any]) -> dict[str, Any]:
        definition = self._definition(resource)
        data = self._values(definition, values, creating=False)
        assignments = [f"{field} = %s" for field in data]
        if definition.updated_column:
            assignments.append(f"{definition.updated_column} = CURRENT_TIMESTAMP")
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"UPDATE {definition.table} SET {', '.join(assignments)} WHERE {definition.id_column} = %s", (*data.values(), record_id))
                if cursor.rowcount == 0:
                    raise MasterDataError("Registro maestro no encontrado", 404)
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se pudo actualizar: existe un valor duplicado o una referencia no valida", 409) from exc
        return self.get(resource, record_id)

    def delete(self, resource: str, record_id: int) -> None:
        definition = self._definition(resource)
        if resource == "clients":
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT EXISTS (SELECT 1 FROM public.clients_addresses WHERE client_id = %s) AS is_in_use", (record_id,))
                if cursor.fetchone()["is_in_use"]:
                    raise MasterDataError("No se puede eliminar un cliente con direcciones asociadas", 409)
        if resource == "suppliers":
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT EXISTS (SELECT 1 FROM public.inventory_suppliers_addresses WHERE supplier_id = %s) AS is_in_use", (record_id,))
                if cursor.fetchone()["is_in_use"]:
                    raise MasterDataError("No se puede eliminar un proveedor con direcciones asociadas", 409)
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {definition.table} WHERE {definition.id_column} = %s", (record_id,))
                if cursor.rowcount == 0:
                    raise MasterDataError("Registro maestro no encontrado", 404)
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se puede eliminar porque el registro tiene dependencias", 409) from exc

    def client_addresses(self, client_id: int) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT 1 FROM public.clients WHERE pk_client = %s", (client_id,))
            if not cursor.fetchone():
                raise MasterDataError("Cliente no encontrado", 404)
            cursor.execute("""SELECT ca.id, ca.address_type, ca.global_address_id, ga.address_line_1, ga.address_line_2,
                ga.city, ga.state_province, ga.postal_code, ga.country_code, ga.country_name, ga.contact_name, ga.contact_phone, ga.contact_email, ga.notes
                FROM public.clients_addresses ca JOIN public.globlal_addresses ga ON ga.id = ca.global_address_id
                WHERE ca.client_id = %s ORDER BY ca.id DESC""", (client_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_client_address(self, client_id: int, global_address_id: int, address_type: str) -> dict[str, Any]:
        allowed = {"Dirección principal", "Dirección por defecto", "Dirección de entrega", "Dirección de Recogida"}
        if address_type not in allowed:
            raise MasterDataError("Tipo de dirección no válido")
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""INSERT INTO public.clients_addresses (client_id, global_address_id, address_type)
                    VALUES (%s, %s, %s) RETURNING id""", (client_id, global_address_id, address_type))
                association_id = int(cursor.fetchone()["id"])
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("No se pudo vincular la dirección al cliente", 409) from exc
        return next(row for row in self.client_addresses(client_id) if row["id"] == association_id)

    def update_client_address(self, client_id: int, association_id: int, address_type: str) -> dict[str, Any]:
        if address_type not in {"Dirección principal", "Dirección por defecto", "Dirección de entrega", "Dirección de Recogida"}:
            raise MasterDataError("Tipo de dirección no válido")
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("UPDATE public.clients_addresses SET address_type = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND client_id = %s", (address_type, association_id, client_id))
                if cursor.rowcount == 0:
                    raise MasterDataError("Dirección del cliente no encontrada", 404)
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("Ya existe esta dirección con ese tipo", 409) from exc
        except MasterDataError:
            self.connection.rollback()
            raise
        return next(row for row in self.client_addresses(client_id) if row["id"] == association_id)

    def delete_client_address(self, client_id: int, association_id: int) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM public.clients_addresses WHERE id = %s AND client_id = %s", (association_id, client_id))
            if cursor.rowcount == 0:
                self.connection.rollback()
                raise MasterDataError("Dirección del cliente no encontrada", 404)
        self.connection.commit()

    def supplier_addresses(self, supplier_id: int) -> list[dict[str, Any]]:
        self.get("suppliers", supplier_id)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""SELECT sa.id, sa.address_type, sa.global_address_id, ga.address_line_1, ga.address_line_2, ga.city, ga.state_province, ga.postal_code, ga.country_code, ga.country_name, ga.contact_name, ga.contact_phone, ga.contact_email, ga.notes FROM public.inventory_suppliers_addresses sa JOIN public.globlal_addresses ga ON ga.id = sa.global_address_id WHERE sa.supplier_id = %s ORDER BY sa.id DESC""", (supplier_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_supplier_address(self, supplier_id: int, global_address_id: int, address_type: str) -> dict[str, Any]:
        if address_type not in {"Dirección principal", "Dirección por defecto", "Dirección de entrega", "Dirección de Recogida"}: raise MasterDataError("Tipo de dirección no válido")
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("INSERT INTO public.inventory_suppliers_addresses (supplier_id, global_address_id, address_type) VALUES (%s, %s, %s) RETURNING id", (supplier_id, global_address_id, address_type)); association_id = int(cursor.fetchone()["id"])
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback(); raise MasterDataError("No se pudo vincular la dirección al proveedor", 409) from exc
        return next(row for row in self.supplier_addresses(supplier_id) if row["id"] == association_id)

    def update_supplier_address(self, supplier_id: int, association_id: int, address_type: str) -> dict[str, Any]:
        if address_type not in {"Dirección principal", "Dirección por defecto", "Dirección de entrega", "Dirección de Recogida"}:
            raise MasterDataError("Tipo de dirección no válido")
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("UPDATE public.inventory_suppliers_addresses SET address_type = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND supplier_id = %s", (address_type, association_id, supplier_id))
                if cursor.rowcount == 0:
                    raise MasterDataError("Dirección del proveedor no encontrada", 404)
            self.connection.commit()
        except psycopg2.IntegrityError as exc:
            self.connection.rollback()
            raise MasterDataError("Ya existe esta dirección con ese tipo", 409) from exc
        except MasterDataError:
            self.connection.rollback()
            raise
        return next(row for row in self.supplier_addresses(supplier_id) if row["id"] == association_id)

    def delete_supplier_address(self, supplier_id: int, association_id: int) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM public.inventory_suppliers_addresses WHERE id = %s AND supplier_id = %s", (association_id, supplier_id))
            if cursor.rowcount == 0: self.connection.rollback(); raise MasterDataError("Dirección del proveedor no encontrada", 404)
        self.connection.commit()
