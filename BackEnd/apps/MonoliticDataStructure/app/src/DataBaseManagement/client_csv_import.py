"""Validación e importación atómica del formato CSV de clientes."""

import csv
import io
from dataclasses import dataclass
from itertools import islice


CSV_COLUMNS = ("code_cliente", "name_client", "description", "tipo_cliente")
ALTERNATE_CSV_COLUMNS = ("code_cliente", "name_client", "description", "tipo cliente")
MAX_CSV_BYTES = 200 * 1024 * 1024
IMPORT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class ClientCsvRow:
    code: str
    name: str
    description: str | None
    client_type: str


def parse_client_csv(content: bytes) -> list[ClientCsvRow]:
    return list(iter_client_csv(io.BytesIO(content)))


def iter_client_csv(source):
    """Lee el archivo subido sin mantener su contenido completo en memoria."""
    source.seek(0, io.SEEK_END)
    if source.tell() > MAX_CSV_BYTES:
        raise ValueError("El CSV supera el límite de 200 MB.")
    source.seek(0)
    text = io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
    try:
        yield from _parse_client_rows(text)
    except UnicodeDecodeError as exc:
            raise ValueError("El CSV debe estar codificado en UTF-8.") from exc
    finally:
        text.detach()


def _parse_client_rows(text):
    reader = csv.reader(text, strict=True)
    count = 0
    seen: set[str] = set()
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
            code, name, description, client_type = (cell.strip() for cell in cells)
            for field, value in (("code_cliente", code), ("name_client", name), ("tipo_cliente", client_type)):
                if not value:
                    raise ValueError(f"Línea {line}: {field} es obligatorio.")
            if code in seen:
                raise ValueError(f"Línea {line}: code_cliente repetido: {code}.")
            if len(name) > 250:
                raise ValueError(f"Línea {line}: name_client no puede superar 250 caracteres.")
            if len(description) > 255:
                raise ValueError(f"Línea {line}: description no puede superar 255 caracteres.")
            if len(client_type) > 250:
                raise ValueError(f"Línea {line}: tipo_cliente no puede superar 250 caracteres.")
            seen.add(code)
            count += 1
            yield ClientCsvRow(code, name, description or None, client_type)
    except csv.Error as exc:
        raise ValueError(f"Línea {reader.line_num}: CSV inválido ({exc}).") from exc
    if not count:
        raise ValueError("El CSV no contiene clientes.")


def import_client_csv(content, connection) -> dict[str, int]:
    for event in import_client_csv_events(content, connection):
        if event["stage"] == "complete":
            return event["result"]
    raise RuntimeError("La importación no ha finalizado.")


def import_client_csv_events(content, connection):
    """Valida todo el CSV y guarda los clientes en una sola transacción."""
    source = io.BytesIO(content) if isinstance(content, bytes) else content
    source.seek(0, io.SEEK_END)
    size = source.tell()
    yield {"stage": "validating", "percent": 0}
    total = 0
    validation = iter_client_csv(source)
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
            cursor.execute("LOCK TABLE public.clients IN SHARE ROW EXCLUSIVE MODE")
            cursor.execute("SELECT pk_type_client, name FROM public.type_client")
            type_ids = {str(name).strip().casefold(): type_id for type_id, name in cursor.fetchall()}
            clients = iter_client_csv(source)
            try:
                while batch := list(islice(clients, IMPORT_BATCH_SIZE)):
                    missing_types = sorted({row.client_type for row in batch if row.client_type.casefold() not in type_ids})
                    if missing_types:
                        raise ValueError("Tipos de cliente no encontrados: " + ", ".join(missing_types))
                    cursor.execute(
                        "SELECT client_code FROM public.clients WHERE client_code = ANY(%s)",
                        ([row.code for row in batch],),
                    )
                    existing = {row[0] for row in cursor.fetchall()}
                    values = [
                        (row.code, row.name, row.description, type_ids[row.client_type.casefold()])
                        for row in batch if row.code not in existing
                    ]
                    if values:
                        placeholders = ",".join(["(%s, %s, %s, %s)"] * len(values))
                        cursor.execute(
                            "INSERT INTO public.clients (client_code, name, description, fk_type_client) VALUES " + placeholders,
                            tuple(value for row in values for value in row),
                        )
                        imported += len(values)
                    processed += len(batch)
                    yield {"stage": "importing", "percent": int(processed * 100 / total),
                           "processed": processed, "total": total}
            finally:
                clients.close()
            yield {"stage": "committing", "percent": 100}
    yield {"stage": "complete", "percent": 100,
           "result": {"imported": imported, "skipped": total - imported, "total": total}}
