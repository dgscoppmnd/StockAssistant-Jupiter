from datetime import datetime, timezone
import logging
from typing import Any

from .dbManagementProducts import (
	count_disabled_products,
	delete_product,
	get_all_products,
	get_disabled_products,
	get_product_by_id,
	insert_product,
	update_product,
)
from .dbManagementProductImages import get_default_product_image_by_product_id
from .schemasProducts import ProductCreate, ProductUpdate


logger = logging.getLogger("api.dbProducts.service")


class ProductServicesManager:
	def __init__(self, db: Any = None):
		self.db = db

	def _clean_text(self, text: str | None) -> str:
		if text is None:
			return ""

		censored_words = ["maldicion", "tonto", "idiota", "malo", "feo"]
		cleaned_text = text.strip()
		for word in censored_words:
			cleaned_text = cleaned_text.replace(word, "****")
		return cleaned_text

	# Campos que se espera que sean numéricos pero podrían venir con formato de texto o símbolos, se limpian y convierten a float.
	_MONEY_FIELDS = ("price", "final_price", "discount")

	@staticmethod
	def _parse_money(value: Any) -> float | None:
		if value is None:
			return None
		if isinstance(value, (int, float)):
			return float(value)
		import re
		cleaned = re.sub(r"[^\d.\-]", "", str(value))
		try:
			return float(cleaned)
		except ValueError:
			return None

	def _serialize_Product(self, row: dict[str, Any]) -> dict[str, Any]:
		result = dict(row)
		for field in self._MONEY_FIELDS:
			if field in result:
				result[field] = self._parse_money(result[field])
		if result.get("fk_currency") is None:
			result["fk_currency"] = 1
		if result.get("fk_last_update_user") is None:
			result["fk_last_update_user"] = 1
		if result.get("user_rating") is None:
			result["user_rating"] = 0.0

		try:
			default_image = get_default_product_image_by_product_id(result["pk_product"], connection=self.db)
			result["default_image_url"] = default_image["public_url"] if default_image else None
		except Exception as exc:
			logger.warning(
				"event=default_product_image_lookup_failed product_id=%s detail=%s",
				result.get("pk_product"),
				str(exc),
			)
			result["default_image_url"] = None
		return result

	def add_Product(self, product_create: ProductCreate) -> dict[str, Any]:
		payload = {
			"cdgo_producto_externo": self._clean_text(product_create.cdgo_producto_externo),
			"name_product": self._clean_text(product_create.name_product),
			"description_product": self._clean_text(product_create.description_product),
			"disabled": product_create.disabled,
			"price": product_create.price,
			"unit": product_create.unit,
			"final_price": product_create.final_price,
			"discount": product_create.discount,
			"discount_end_date": product_create.discount_end_date,
			"fk_currency": product_create.fk_currency,
			"currency": self._clean_text(product_create.currency),
			"user_rating": product_create.user_rating,
			"link": self._clean_text(product_create.link),
			"creation_date": product_create.creation_date,
			"fk_last_update_user": product_create.fk_last_update_user,
			"last_update": product_create.last_update,
			"supplier": self._clean_text(product_create.supplier),
		}
		created = insert_product(payload, connection=self.db)
		return self._serialize_Product(created)

	def get_Product(self, product_id: int) -> dict[str, Any]:
		row = get_product_by_id(product_id, connection=self.db)
		if not row:
			raise ValueError(f"Producto con ID {product_id} no encontrado")
		return self._serialize_Product(row)

	def get_all_Products(self) -> list[dict[str, Any]]:
		rows = get_all_products(connection=self.db)
		return [self._serialize_Product(row) for row in rows]

	def set_Product_status(self, product_id: int) -> dict[str, Any]:
		updated = update_product(
			product_id,
			{
				"disabled": True,
				"last_update": datetime.now(timezone.utc),
			},
			connection=self.db,
		)
		if not updated:
			raise ValueError(f"Producto con ID {product_id} no encontrado")
		return self._serialize_Product(updated)

	def update_Product(self, product_id: int, product_update: ProductUpdate) -> dict[str, Any]:
		payload = {
			"cdgo_producto_externo": self._clean_text(product_update.cdgo_producto_externo),
			"name_product": self._clean_text(product_update.name_product),
			"description_product": self._clean_text(product_update.description_product),
			"disabled": product_update.disabled,
			"price": product_update.price,
			"unit": product_update.unit,
			"final_price": product_update.final_price,
			"discount": product_update.discount,
			"discount_end_date": product_update.discount_end_date,
			"fk_currency": product_update.fk_currency,
			"currency": self._clean_text(product_update.currency),
			"user_rating": product_update.user_rating,
			"link": self._clean_text(product_update.link),
			"creation_date": product_update.creation_date,
			"fk_last_update_user": product_update.fk_last_update_user,
			"last_update": datetime.now(timezone.utc),
			"supplier": self._clean_text(product_update.supplier),
		}

		updated = update_product(product_id, payload, connection=self.db)
		if not updated:
			raise ValueError(f"Producto con ID {product_id} no encontrado")
		return self._serialize_Product(updated)

	def delete_Product(self, product_id: int) -> bool:
		deleted = delete_product(product_id, connection=self.db)
		if not deleted:
			raise ValueError(f"Producto con ID {product_id} no encontrado")
		return True

	def get_disabled_Products(self) -> list[dict[str, Any]]:
		rows = get_disabled_products(connection=self.db)
		return [self._serialize_Product(row) for row in rows]

	def count_disabled_Products(self) -> int:
		return count_disabled_products(connection=self.db)
