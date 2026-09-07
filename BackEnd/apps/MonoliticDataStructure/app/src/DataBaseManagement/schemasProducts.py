from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
	cdgo_producto_externo: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Codigo externo del producto")
	name_product: str = Field(min_length=1, max_length=200, description="Nombre del producto")
	description_product: Optional[str] = Field(default=None, min_length=1, max_length=1000, description="Descripcion del producto")
	disabled: bool = Field(default=False, description="Estado del producto")
	price: Optional[float] = Field(default=0, description="Precio base")
	unit: int = Field(default=1, description="Unidad del producto")
	final_price: Optional[float] = Field(default=0, description="Precio final")
	discount: Optional[float] = Field(default=0, description="Descuento")
	discount_end_date: Optional[datetime] = Field(default=None, description="Fecha de fin del descuento")
	fk_currency: int = Field(default=1, description="ID de moneda")
	currency: Optional[str] = Field(default=None, min_length=1, max_length=50, description="Moneda")
	user_rating: float = Field(default=0, description="Calificacion de usuario")
	link: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Enlace del producto")
	creation_date: Optional[datetime] = Field(default=None, description="Fecha de creacion")
	fk_last_update_user: int = Field(default=1, description="Usuario de ultima actualizacion")
	last_update: Optional[datetime] = Field(default=None, description="Fecha de ultima actualizacion")
	supplier: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Proveedor")


class ProductUpdate(BaseModel):
	cdgo_producto_externo: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Edita codigo externo del producto")
	name_product: str = Field(min_length=1, max_length=200, description="Edita nombre del producto")
	description_product: Optional[str] = Field(default=None, min_length=1, max_length=1000, description="Edita descripcion del producto")
	disabled: bool = Field(default=False, description="Edita estado del producto")
	price: Optional[float] = Field(default=0, description="Edita precio base")
	unit: int = Field(default=1, description="Edita unidad del producto")
	final_price: Optional[float] = Field(default=0, description="Edita precio final")
	discount: Optional[float] = Field(default=0, description="Edita descuento")
	discount_end_date: Optional[datetime] = Field(default=None, description="Edita fecha de fin del descuento")
	fk_currency: int = Field(default=1, description="Edita ID de moneda")
	currency: Optional[str] = Field(default=None, min_length=1, max_length=50, description="Edita moneda")
	user_rating: float = Field(default=0, description="Edita calificacion de usuario")
	link: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Edita enlace del producto")
	creation_date: Optional[datetime] = Field(default=None, description="Edita fecha de creacion")
	fk_last_update_user: int = Field(default=1, description="Edita usuario de ultima actualizacion")
	last_update: Optional[datetime] = Field(default=None, description="Edita fecha de ultima actualizacion")
	supplier: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Edita proveedor")


class ProductResponse(BaseModel):
	pk_product: int
	cdgo_producto_externo: Optional[str] = None
	name_product: str
	description_product: Optional[str] = None
	disabled: bool
	price: Optional[float] = None
	unit: int
	final_price: Optional[float] = None
	discount: Optional[float] = None
	discount_end_date: Optional[datetime] = None
	fk_currency: int
	currency: Optional[str] = None
	user_rating: float
	link: Optional[str] = None
	creation_date: Optional[datetime] = None
	fk_last_update_user: int
	last_update: Optional[datetime] = None
	supplier: Optional[str] = None
	default_image_url: Optional[str] = None

	class Config:
		from_attributes = True


class ProductImageResponse(BaseModel):
	id: int
	product_id: Optional[int] = None
	url: str
	mime_type: str
	file_size: int
	original_filename: Optional[str] = None
	is_default: bool
	created_at: datetime

	class Config:
		from_attributes = True


class ProductImageUploadResponse(ProductImageResponse):
	pass
