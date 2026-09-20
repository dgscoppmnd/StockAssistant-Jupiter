import logging
import json
import os
import uuid
from itertools import islice
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from DataBaseManagement.product_csv_import import (
	IMPORT_BATCH_SIZE,
	MAX_CSV_BYTES,
	import_product_csv,
	import_product_csv_events,
	iter_product_csv,
)
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from DataBaseManagement.dbConectionPostgres import db_context, get_db_products
from DataBaseManagement.dbManagementProductImages import (
	delete_product_image,
	get_default_product_image_by_product_id,
	get_product_image_by_id,
	get_product_images_by_product_id,
	insert_product_image,
	set_default_product_image,
)
from DataBaseManagement.dbservicesProducts import ProductServicesManager
from DataBaseManagement.dbManagementProducts import (
	count_active_products,
	get_product_option,
	get_products_by_external_codes,
	iter_active_product_batches,
	search_product_options,
)
from DataBaseManagement.schemasProducts import (
	ProductCreate,
	ProductImageResponse,
	ProductImageUploadResponse,
	ProductResponse,
	ProductPageResponse,
	ProductOptionsResponse,
	ProductOptionResponse,
	ProductUpdate,
)

router = APIRouter()
logger = logging.getLogger("api.endpointsProducts")

PRODUCT_IMAGE_MAX_BYTES = int(os.getenv("PRODUCT_IMAGE_MAX_BYTES", str(100 * 1024 * 1024)))
PRODUCT_IMAGE_UPLOAD_DIR = Path("/app/data/uploads/products")
ALLOWED_IMAGE_CONTENT_TYPES: dict[str, str] = {
	"image/png": ".png",
	"image/jpeg": ".jpg",
	"image/jpg": ".jpg",
	"image/webp": ".webp",
	"image/gif": ".gif",
	"image/svg+xml": ".svg",
}


def _sync_product_vector(product: dict) -> tuple[bool, str | None]:
	"""Sincroniza un alta/cambio sin convertir un fallo vectorial en un falso rollback SQL."""
	try:
		from src.vector_store.product_indexer import delete_product_record, upsert_product_records

		if product.get("disabled"):
			delete_product_record(int(product["pk_product"]))
		else:
			upsert_product_records([product])
		return True, None
	except Exception as exc:
		logger.exception(
			"event=product_vector_sync_failed product_id=%s",
			product.get("pk_product"),
		)
		return False, str(exc)


def _iter_imported_product_vector_counts(source, db):
	"""Relee el CSV ya confirmado y sincroniza sus productos en memoria acotada."""
	from src.vector_store.product_indexer import iter_upsert_product_records

	def database_rows():
		products = iter_product_csv(source)
		try:
			while batch := list(islice(products, IMPORT_BATCH_SIZE)):
				codes = [product.cdgo_producto_externo for product in batch]
				yield from get_products_by_external_codes(codes, connection=db)
		finally:
			products.close()

	yield from iter_upsert_product_records(database_rows())


def _sync_imported_product_vectors(source, db) -> int:
	indexed = 0
	for indexed in _iter_imported_product_vector_counts(source, db):
		pass
	return indexed


def _add_vector_result(result: dict, source, db) -> dict:
	try:
		result["indexed"] = _sync_imported_product_vectors(source, db)
		result["index_error"] = None
	except Exception as exc:
		logger.exception("event=import_products_vector_sync_failed")
		result["indexed"] = 0
		result["index_error"] = str(exc)
	return result


def _stream_full_product_vector_sync():
	"""Sincroniza todos los productos activos y emite progreso NDJSON."""
	try:
		from src.vector_store.product_indexer import iter_upsert_product_records

		with db_context() as db:
			total = count_active_products(db)
			yield json.dumps({"stage": "indexing", "percent": 0, "processed": 0, "total": total}) + "\n"

			def products():
				for batch in iter_active_product_batches(db):
					yield from batch

			indexed = 0
			for indexed in iter_upsert_product_records(products()):
				percent = 100 if total == 0 else min(99, int(indexed * 100 / total))
				yield json.dumps({
					"stage": "indexing",
					"percent": percent,
					"processed": indexed,
					"total": total,
				}) + "\n"
			yield json.dumps({
				"stage": "complete",
				"percent": 100,
				"processed": indexed,
				"total": total,
				"result": {"indexed": indexed, "total": total},
			}) + "\n"
		logger.info("event=full_product_vector_sync_success indexed=%s total=%s", indexed, total)
	except Exception as exc:
		logger.exception("event=full_product_vector_sync_failed")
		yield json.dumps({"stage": "error", "detail": str(exc)}, ensure_ascii=False) + "\n"


def _content_type_to_extension(content_type: str) -> str:
	extension = ALLOWED_IMAGE_CONTENT_TYPES.get(content_type.lower())
	if extension:
		return extension
	raise HTTPException(
		status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
		detail=f"Tipo de imagen no soportado: {content_type or 'desconocido'}",
	)


def _to_product_image_response(image_row: dict) -> dict:
	return {
		"id": image_row["id"],
		"product_id": image_row.get("product_id"),
		"url": image_row["public_url"],
		"mime_type": image_row["mime_type"],
		"file_size": image_row["file_size"],
		"original_filename": image_row.get("original_filename"),
		"is_default": bool(image_row.get("is_default")),
		"created_at": image_row["created_at"],
	}


@router.post("/products/{product_id}/images/upload", response_model=ProductImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def subir_imagen_producto(
	product_id: int,
	file: UploadFile = File(...),
	make_default: bool = Query(default=False),
	db=Depends(get_db_products),
):
	logger.info("event=upload_product_image_start filename=%s product_id=%s", file.filename, product_id)
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		manager.get_Product(product_id)
	except ValueError:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Producto con ID {product_id} no encontrado",
		)

	content_type = (file.content_type or "").strip().lower()
	extension = _content_type_to_extension(content_type)

	PRODUCT_IMAGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
	stored_filename = f"{uuid.uuid4().hex}{extension}"
	stored_path = PRODUCT_IMAGE_UPLOAD_DIR / stored_filename

	bytes_written = 0
	chunk_size = 1024 * 1024

	try:
		with stored_path.open("wb") as output:
			while True:
				chunk = await file.read(chunk_size)
				if not chunk:
					break
				bytes_written += len(chunk)
				if bytes_written > PRODUCT_IMAGE_MAX_BYTES:
					raise HTTPException(
						status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
						detail=f"La imagen supera el limite permitido de {PRODUCT_IMAGE_MAX_BYTES // (1024 * 1024)}MB",
					)
				output.write(chunk)
	except HTTPException:
		if stored_path.exists():
			stored_path.unlink(missing_ok=True)
		raise
	except Exception as exc:
		if stored_path.exists():
			stored_path.unlink(missing_ok=True)
		logger.exception("event=upload_product_image_error filename=%s", file.filename)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"No se pudo guardar la imagen: {str(exc)}",
		)
	finally:
		await file.close()

	public_url = f"/api/media/products/{stored_filename}"
	created_image = insert_product_image(
		{
			"product_id": product_id,
			"original_filename": file.filename,
			"stored_filename": stored_filename,
			"mime_type": content_type,
			"file_size": bytes_written,
			"storage_path": str(stored_path),
			"public_url": public_url,
			"is_default": False,
		},
		connection=db,
	)

	existing_default = get_default_product_image_by_product_id(product_id, connection=db)
	if make_default or existing_default is None:
		set_default_product_image(created_image["id"], product_id, connection=db)
		created_image = get_product_image_by_id(created_image["id"], connection=db) or created_image

	logger.info(
		"event=upload_product_image_success image_id=%s product_id=%s bytes=%s",
		created_image.get("id"),
		product_id,
		bytes_written,
	)
	return _to_product_image_response(created_image)


@router.get("/products/{product_id}/images", response_model=list[ProductImageResponse])
def listar_imagenes_producto(product_id: int, db=Depends(get_db_products)):
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		manager.get_Product(product_id)
	except ValueError:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Producto con ID {product_id} no encontrado",
		)

	rows = get_product_images_by_product_id(product_id, connection=db)
	return [_to_product_image_response(row) for row in rows]


@router.put("/products/{product_id}/images/{image_id}/default", response_model=ProductImageResponse)
def seleccionar_imagen_default_producto(product_id: int, image_id: int, db=Depends(get_db_products)):
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		manager.get_Product(product_id)
	except ValueError:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Producto con ID {product_id} no encontrado",
		)

	updated = set_default_product_image(image_id=image_id, product_id=product_id, connection=db)
	if not updated:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Imagen con ID {image_id} no encontrada para el producto {product_id}",
		)
	return _to_product_image_response(updated)


@router.delete("/products/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_imagen_producto(product_id: int, image_id: int, db=Depends(get_db_products)):
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		manager.get_Product(product_id)
	except ValueError:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Producto con ID {product_id} no encontrado",
		)

	image = get_product_image_by_id(image_id, connection=db)
	if not image or image.get("product_id") != product_id:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Imagen con ID {image_id} no encontrada para el producto {product_id}",
		)

	storage_path = Path(image["storage_path"])
	deleted = delete_product_image(image_id, connection=db)
	if not deleted:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Imagen con ID {image_id} no encontrada",
		)

	if storage_path.exists():
		storage_path.unlink(missing_ok=True)

	if image.get("is_default"):
		next_image = get_product_images_by_product_id(product_id, connection=db)
		if next_image:
			set_default_product_image(next_image[0]["id"], product_id, connection=db)

	return None


@router.post("/products/sync-qdrant")
def sincronizar_productos_qdrant():
	logger.info("event=full_product_vector_sync_start")
	return StreamingResponse(
		_stream_full_product_vector_sync(),
		media_type="application/x-ndjson",
		headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
	)


@router.post("/products/import-csv")
async def importar_productos_csv(file: UploadFile = File(...), progress: bool = Query(default=False)):
	try:
		if not (file.filename or "").lower().endswith(".csv"):
			raise HTTPException(status_code=400, detail="Selecciona un archivo .csv.")
		if file.size is not None and file.size > MAX_CSV_BYTES:
			raise HTTPException(status_code=413, detail="El CSV supera el límite de 200 MB.")
		if progress:
			# Descriptor independiente: sigue abierto aunque FastAPI cierre UploadFile.
			source = await run_in_threadpool(_duplicate_csv_file, file.file)
			return StreamingResponse(
				_stream_product_import(source), media_type="application/x-ndjson",
				headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
			)
		return await run_in_threadpool(_import_product_file, file.file)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except HTTPException:
		raise
	except Exception as exc:
		logger.exception("event=import_products_csv_failed")
		raise HTTPException(status_code=500, detail="No se pudo importar el CSV. No se ha guardado ningún producto.") from exc
	finally:
		await file.close()


def _duplicate_csv_file(source):
	source.seek(0)
	return os.fdopen(os.dup(source.fileno()), "rb")


def _import_product_file(source):
	with db_context() as db:
		result = import_product_csv(source, db)
		return _add_vector_result(result, source, db)


def _stream_product_import(source):
	with source:
		try:
			with db_context() as db:
				completion = None
				for event in import_product_csv_events(source, db):
					if event["stage"] == "complete":
						completion = event
					else:
						yield json.dumps(event, ensure_ascii=False) + "\n"
				if completion is None:
					raise RuntimeError("La importación no ha finalizado.")
				yield json.dumps({"stage": "indexing", "percent": 0}, ensure_ascii=False) + "\n"
				try:
					indexed = 0
					total = max(int(completion["result"]["total"]), 1)
					for indexed in _iter_imported_product_vector_counts(source, db):
						yield json.dumps(
							{"stage": "indexing", "percent": min(99, int(indexed * 100 / total)), "processed": indexed, "total": total},
							ensure_ascii=False,
						) + "\n"
					completion["result"]["indexed"] = indexed
					completion["result"]["index_error"] = None
				except Exception as exc:
					logger.exception("event=import_products_vector_sync_failed")
					completion["result"]["indexed"] = 0
					completion["result"]["index_error"] = str(exc)
				yield json.dumps({"stage": "indexing", "percent": 100}, ensure_ascii=False) + "\n"
				yield json.dumps(completion, ensure_ascii=False) + "\n"
		except ValueError as exc:
			yield json.dumps({"stage": "error", "detail": str(exc)}, ensure_ascii=False) + "\n"
		except Exception:
			logger.exception("event=import_products_csv_failed")
			yield json.dumps({"stage": "error", "detail": "No se pudo importar el CSV. No se ha guardado ningún producto."}) + "\n"


@router.post("/products/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def crear_producto(product: ProductCreate, db=Depends(get_db_products)):
	logger.info("event=create_product_start name=%s", product.name_product)
	manager: ProductServicesManager = ProductServicesManager(db)
	created_product = manager.add_Product(product)
	created_product["semantic_indexed"], created_product["semantic_index_error"] = _sync_product_vector(created_product)
	logger.info("event=create_product_success product_id=%s", created_product.get("pk_product"))
	return created_product


@router.put("/products/{product_id}", response_model=ProductResponse, status_code=status.HTTP_202_ACCEPTED)
def actualizar_producto(product_id: int, product_update: ProductUpdate, db=Depends(get_db_products)):
	logger.info("event=update_product_start product_id=%s", product_id)
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		updated_product = manager.update_Product(product_id, product_update)
		updated_product["semantic_indexed"], updated_product["semantic_index_error"] = _sync_product_vector(updated_product)
		logger.info("event=update_product_success product_id=%s", product_id)
		return updated_product
	except ValueError as e:
		logger.warning("event=update_product_not_found product_id=%s detail=%s", product_id, str(e))
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_producto(product_id: int, db=Depends(get_db_products)):
	logger.info("event=delete_product_start product_id=%s", product_id)
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		manager.delete_Product(product_id)
		try:
			from src.vector_store.product_indexer import delete_product_record
			delete_product_record(product_id)
		except Exception:
			logger.exception("event=delete_product_vector_sync_failed product_id=%s", product_id)
		logger.info("event=delete_product_success product_id=%s", product_id)
	except ValueError as e:
		logger.warning("event=delete_product_not_found product_id=%s detail=%s", product_id, str(e))
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
	return None


@router.put("/products/status/{product_id}", response_model=ProductResponse)
def set_product_status(product_id: int, db=Depends(get_db_products)):
	logger.info("event=set_product_status product_id=%s", product_id)
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		updated_product = manager.set_Product_status(product_id)
		updated_product["semantic_indexed"], updated_product["semantic_index_error"] = _sync_product_vector(updated_product)
		logger.info("event=set_product_status_success product_id=%s", product_id)
		return updated_product
	except ValueError as e:
		logger.warning("event=set_product_status_not_found product_id=%s detail=%s", product_id, str(e))
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/products/", response_model=list[ProductResponse])
def listar_productos(db=Depends(get_db_products)):
	logger.info("event=list_products")
	manager: ProductServicesManager = ProductServicesManager(db)
	return manager.get_all_Products()


@router.get("/products/deshabilitados", response_model=list[ProductResponse])
def obtener_productos_deshabilitados(db=Depends(get_db_products)):
	logger.info("event=list_disabled_products")
	manager: ProductServicesManager = ProductServicesManager(db)
	return manager.get_disabled_Products()


@router.get("/products/deshabilitados/count")
def contar_deshabilitados(db=Depends(get_db_products)):
	logger.info("event=count_disabled_products")
	manager: ProductServicesManager = ProductServicesManager(db)
	return {"disabled": manager.count_disabled_Products()}


@router.get("/products/page", response_model=ProductPageResponse)
def listar_productos_paginados(
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=10, ge=1, le=100),
	db=Depends(get_db_products),
):
	return ProductServicesManager(db).get_Products_page(page, page_size)


@router.get("/products/options", response_model=ProductOptionsResponse)
def buscar_opciones_productos(
	q: str = Query(default="", max_length=200),
	after: int = Query(default=0, ge=0),
	limit: int = Query(default=10, ge=1, le=50),
	db=Depends(get_db_products),
):
	return search_product_options(q, after, limit, db)


@router.get("/products/options/{product_id}", response_model=ProductOptionResponse)
def obtener_opcion_producto(product_id: int, db=Depends(get_db_products)):
	product = get_product_option(product_id, db)
	if product is None:
		raise HTTPException(status_code=404, detail="Producto no encontrado")
	return product


@router.get("/products/{product_id}", response_model=ProductResponse)
def obtener_producto(product_id: int, db=Depends(get_db_products)):
	logger.info("event=get_product_start product_id=%s", product_id)
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		product = manager.get_Product(product_id)
		logger.info("event=get_product_success product_id=%s", product_id)
		return product
	except ValueError as e:
		logger.warning("event=get_product_not_found product_id=%s detail=%s", product_id, str(e))
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
