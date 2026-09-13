"""Validación e importación atómica del formato CSV de productos."""

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from itertools import islice

from pydantic import ValidationError

from .schemasProducts import ProductCreate

CSV_COLUMNS = (
    "product_id", "product_name", "description", "product_category", "brand",
    "sku", "product_cost_usd", "selling_price_usd", "created_at",
)
MAX_CSV_BYTES = 200 * 1024 * 1024
IMPORT_BATCH_SIZE = 1000


def parse_product_csv(content: bytes) -> list[ProductCreate]:
    return list(iter_product_csv(io.BytesIO(content)))


def iter_product_csv(source):
    """Lee el archivo subido sin mantener su contenido completo en memoria."""
    source.seek(0, io.SEEK_END)
    if source.tell() > MAX_CSV_BYTES:
        raise ValueError("El CSV supera el límite de 200 MB.")
    source.seek(0)
    text = io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
    try:
        yield from _parse_product_rows(text)
    except UnicodeDecodeError as exc:
        raise ValueError("El CSV debe estar codificado en UTF-8.") from exc
    finally:
        text.detach()  # El archivo pertenece a UploadFile y se cierra en el endpoint.


def _parse_product_rows(text):
    reader = csv.reader(text, strict=True)
    count = 0
    seen = set()
    try:
        header = next(reader, [])
        if tuple(header) != CSV_COLUMNS:
            raise ValueError("La cabecera debe ser: " + ",".join(CSV_COLUMNS))
        for cells in reader:
            if not cells or all(not cell.strip() for cell in cells):
                continue
            line = reader.line_num
            if any("\x00" in cell for cell in cells):
                raise ValueError(f"Línea {line}: el archivo contiene caracteres no válidos.")
            if len(cells) != len(CSV_COLUMNS):
                raise ValueError(f"Línea {line}: se esperaban 9 columnas.")
            row = dict(zip(CSV_COLUMNS, (cell.strip() for cell in cells)))
            for field in ("product_id", "product_name", "created_at"):
                if not row[field]:
                    raise ValueError(f"Línea {line}: {field} es obligatorio.")
            if row["product_id"] in seen:
                raise ValueError(f"Línea {line}: product_id repetido: {row['product_id']}.")
            prices = []
            for field in ("product_cost_usd", "selling_price_usd"):
                try:
                    price = Decimal(row[field])
                except InvalidOperation as exc:
                    raise ValueError(f"Línea {line}: {field} debe ser un número decimal.") from exc
                if not price.is_finite() or price < 0 or price >= Decimal("99999999999999.9999"):
                    raise ValueError(f"Línea {line}: {field} está fuera del rango permitido.")
                prices.append(float(price))
            try:
                created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ValueError(f"Línea {line}: created_at debe tener formato AAAA-MM-DD HH:MM:SS.") from exc
            description = "\n".join(filter(None, [
                row["description"],
                f"Categoría: {row['product_category']}" if row["product_category"] else "",
                f"Marca: {row['brand']}" if row["brand"] else "",
                f"SKU: {row['sku']}" if row["sku"] else "",
            ]))
            try:
                product = ProductCreate(
                    cdgo_producto_externo=row["product_id"], name_product=row["product_name"],
                    description_product=description or None, price=prices[0], final_price=prices[1],
                    currency="USD", creation_date=created_at,
                )
            except ValidationError as exc:
                details = "; ".join(f"{error['loc'][0]}: {error['msg']}" for error in exc.errors())
                raise ValueError(f"Línea {line}: {details}") from exc
            seen.add(row["product_id"])
            count += 1
            yield product
    except csv.Error as exc:
        raise ValueError(f"Línea {reader.line_num}: CSV inválido ({exc}).") from exc
    if not count:
        raise ValueError("El CSV no contiene productos.")


def import_product_csv(content, connection) -> dict[str, int]:
    for event in import_product_csv_events(content, connection):
        if event["stage"] == "complete":
            return event["result"]
    raise RuntimeError("La importación no ha finalizado.")


def import_product_csv_events(content, connection):
    """Progreso por etapas; complete solo se emite después del commit."""
    source = io.BytesIO(content) if isinstance(content, bytes) else content
    source.seek(0, io.SEEK_END)
    size = source.tell()
    # Validar antes de bloquear la tabla, sin acumular modelos de productos.
    yield {"stage": "validating", "percent": 0}
    total = 0
    validation = iter_product_csv(source)
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
    # Una sola transacción: ningún producto queda guardado si falla el lote.
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("LOCK TABLE public.productos IN SHARE ROW EXCLUSIVE MODE")
            cursor.execute("SELECT id FROM public.inventory_currencies WHERE iso_code = %s", ("USD",))
            currency = cursor.fetchone()
            if currency is None:
                raise ValueError("La moneda USD debe existir en el catálogo de monedas antes de importar.")
            products = iter_product_csv(source)
            try:
                while batch := list(islice(products, IMPORT_BATCH_SIZE)):
                    cursor.execute(
                        "SELECT cdgo_producto_externo FROM public.productos WHERE cdgo_producto_externo = ANY(%s)",
                        ([product.cdgo_producto_externo for product in batch],),
                    )
                    existing = {row[0] for row in cursor.fetchall()}
                    values = [
                        (product.cdgo_producto_externo, product.name_product, product.description_product,
                         product.price, product.final_price, product.currency, product.creation_date, currency[0])
                        for product in batch if product.cdgo_producto_externo not in existing
                    ]
                    if values:
                        placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s)"] * len(values))
                        cursor.execute(
                            """INSERT INTO public.productos
                            (cdgo_producto_externo, name_product, description_product, price,
                             final_price, currency, creation_date, fk_currency) VALUES """ + placeholders,
                            tuple(value for row in values for value in row),
                        )
                        imported += len(values)
                    processed += len(batch)
                    yield {"stage": "importing", "percent": int(processed * 100 / total),
                           "processed": processed, "total": total}
            finally:
                products.close()
            yield {"stage": "committing", "percent": 100}
    yield {"stage": "complete", "percent": 100,
           "result": {"imported": imported, "skipped": total - imported, "total": total}}
