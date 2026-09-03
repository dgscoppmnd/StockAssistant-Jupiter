import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.dbManagementProductImages import (
	delete_product_image,
	get_default_product_image_by_product_id,
	get_product_image_by_id,
	get_product_images_by_product_id,
	insert_product_image,
	set_default_product_image,
)
from DataBaseManagement.dbservicesProducts import ProductServicesManager
from DataBaseManagement.schemasProducts import (
	ProductCreate,
	ProductImageResponse,
	ProductImageUploadResponse,
	ProductResponse,
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


@router.post("/products/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def crear_producto(product: ProductCreate, db=Depends(get_db_products)):
	logger.info("event=create_product_start name=%s", product.name_product)
	manager: ProductServicesManager = ProductServicesManager(db)
	created_product = manager.add_Product(product)
	logger.info("event=create_product_success product_id=%s", created_product.get("pk_product"))
	return created_product


@router.put("/products/{product_id}", response_model=ProductResponse, status_code=status.HTTP_202_ACCEPTED)
def actualizar_producto(product_id: int, product_update: ProductUpdate, db=Depends(get_db_products)):
	logger.info("event=update_product_start product_id=%s", product_id)
	manager: ProductServicesManager = ProductServicesManager(db)
	try:
		updated_product = manager.update_Product(product_id, product_update)
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
