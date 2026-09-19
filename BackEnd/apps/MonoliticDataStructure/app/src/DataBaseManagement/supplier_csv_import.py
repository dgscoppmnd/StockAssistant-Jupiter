"""Validación e importación atómica del formato CSV de proveedores."""

import csv
import io
from dataclasses import dataclass
from itertools import islice


CSV_COLUMNS = ("supplier_code", "name", "email", "phone")
ALTERNATE_CSV_COLUMNS = ("code_proveedor", "name_supplier", "email", "phone")
MAX_CSV_BYTES = 200 * 1024 * 1024
IMPORT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class SupplierCsvRow:
    code: str
    name: str
    email: str | None
    phone: str | None


def parse_supplier_csv(content: bytes) -> list[SupplierCsvRow]:
    return list(iter_supplier_csv(io.BytesIO(content)))


def iter_supplier_csv(source):
    """Lee el archivo subido sin mantener su contenido completo en memoria."""
    source.seek(0, io.SEEK_END)
    if source.tell() > MAX_CSV_BYTES:
        raise ValueError("El CSV supera el límite de 200 MB.")
    source.seek(0)
    text = io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
    try:
        yield from _parse_supplier_rows(text)
    except UnicodeDecodeError as exc:
        raise ValueError("El CSV debe estar codificado en UTF-8.") from exc
    finally:
        text.detach()


def _parse_supplier_rows(text):
    reader = csv.reader(text, strict=True)
    count = 0
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    try:
        header = tuple(cell.strip() for cell in next(reader, []))
        if header not in (CSV_COLUMNS, ALTERNATE_CSV_COLUMNS):
            raise ValueError("La cabecera debe ser: " + ",".join(CSV_COLUMNS))
        for cells in reader:
            if not cells or all(not cell.strip() for cell in cells):
                continue
            line = reader.line_num
            if any("\x00" in cell for cell in cells):
                raise ValueError(f"Línea {line}: el archivo contiene caracteres no válidos.")
            if len(cells) != len(CSV_COLUMNS):
                raise ValueError(f"Línea {line}: se esperaban 4 columnas.")
            code, name, email, phone = (cell.strip() for cell in cells)
            if not code:
                raise ValueError(f"Línea {line}: supplier_code es obligatorio.")
            if not name:
                raise ValueError(f"Línea {line}: name es obligatorio.")
            if code in seen_codes:
                raise ValueError(f"Línea {line}: supplier_code repetido: {code}.")
            normalized_name = name.casefold()
            if normalized_name in seen_names:
                raise ValueError(f"Línea {line}: name repetido: {name}.")
            limits = (("supplier_code", code, 80), ("name", name, 200),
                      ("email", email, 255), ("phone", phone, 80))
            for field, value, maximum in limits:
                if len(value) > maximum:
                    raise ValueError(f"Línea {line}: {field} no puede superar {maximum} caracteres.")
            seen_codes.add(code)
            seen_names.add(normalized_name)
            count += 1
            yield SupplierCsvRow(code, name, email or None, phone or None)
    except csv.Error as exc:
        raise ValueError(f"Línea {reader.line_num}: CSV inválido ({exc}).") from exc
    if not count:
        raise ValueError("El CSV no contiene proveedores.")


def import_supplier_csv(content, connection) -> dict[str, int]:
    for event in import_supplier_csv_events(content, connection):
        if event["stage"] == "complete":
            return event["result"]
    raise RuntimeError("La importación no ha finalizado.")


def import_supplier_csv_events(content, connection):
    """Valida todo el CSV y guarda los proveedores en una sola transacción."""
    source = io.BytesIO(content) if isinstance(content, bytes) else content
    source.seek(0, io.SEEK_END)
    size = source.tell()
    yield {"stage": "validating", "percent": 0}
    total = 0
    validation = iter_supplier_csv(source)
    try:
        for _ in validation:
            total += 1
            if total % IMPORT_BATCH_SIZE == 0:
                yield {"stage": "validating", "percent": min(99, int(source.tell() * 100 / max(size, 1)))}
    finally:
        validation.close()
    yield {"stage": "validating", "percent": 100}
    yield {"stage": "importing", "percent": 0, "processed": 0, "total": total}

    imported = 0
    processed = 0
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("LOCK TABLE public.inventory_suppliers IN SHARE ROW EXCLUSIVE MODE")
            suppliers = iter_supplier_csv(source)
            try:
                while batch := list(islice(suppliers, IMPORT_BATCH_SIZE)):
                    cursor.execute(
                        "SELECT supplier_code, name FROM public.inventory_suppliers "
                        "WHERE supplier_code = ANY(%s) OR name = ANY(%s)",
                        ([row.code for row in batch], [row.name for row in batch]),
                    )
                    existing_rows = cursor.fetchall()
                    existing_codes = {row[0] for row in existing_rows if row[0] is not None}
                    existing_names = {row[1] for row in existing_rows}
                    conflicting_names = sorted({
                        row.name for row in batch
                        if row.name in existing_names and row.code not in existing_codes
                    })
                    if conflicting_names:
                        raise ValueError("Ya existen proveedores con estos nombres y otro código: " + ", ".join(conflicting_names))
                    values = [
                        (row.code, row.name, row.email, row.phone)
                        for row in batch if row.code not in existing_codes
                    ]
                    if values:
                        placeholders = ",".join(["(%s, %s, %s, %s)"] * len(values))
                        cursor.execute(
                            "INSERT INTO public.inventory_suppliers (supplier_code, name, email, phone) VALUES " + placeholders,
                            tuple(value for row in values for value in row),
                        )
                        imported += len(values)
                    processed += len(batch)
                    yield {"stage": "importing", "percent": int(processed * 100 / total),
                           "processed": processed, "total": total}
            finally:
                suppliers.close()
            yield {"stage": "committing", "percent": 100}
    yield {"stage": "complete", "percent": 100,
           "result": {"imported": imported, "skipped": total - imported, "total": total}}
