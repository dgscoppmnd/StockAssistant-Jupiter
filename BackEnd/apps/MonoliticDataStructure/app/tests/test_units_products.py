from datetime import date

# Importamos HTTPException para verificar las respuestas de error 404.
from fastapi import HTTPException

# Importamos los endpoints relacionados con la gestión de productos.
from src.api.routes.products import (
    get_brands,
    get_categories,
    get_product,
    get_product_by_sku,
    get_products

)

# pytest permite definir y ejecutar las pruebas unitarias asíncronas.
import pytest

# MagicMock nos permite crear objetos simulados de la base de datos y sus consultas.
from unittest.mock import MagicMock


# Pruebas unitarias para el endpoint de listado y filtrado de productos.
class TestProducts:
    # Verifica que al no enviar parámetros de filtro (categoría, marca, búsqueda), no se aplique .filter() en SQLAlchemy.
    @pytest.mark.asyncio
    async def test_get_products_with_none(self):
        # Mocks para la sesión de BD y el constructor de consultas.
        db = MagicMock()
        query = MagicMock()

        # Configuración del encadenamiento de métodos de SQLAlchemy.
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos un conjunto de resultados vacío.
        query.count.return_value = 0 
        query.all.return_value = []
        
        # Ejecutamos el endpoint pasándole valores nulos en los filtros opcionales.
        await get_products(
            skip=0,
            limit=0,
            db=db,
            category=None,
            brand=None,
            search=None
        )
        
        # Confirmamos que la cláusula .filter() no haya sido invocada.
        query.filter.assert_not_called()

    # Valida el correcto retorno y mapeo de la lista paginada cuando existen productos en la BD.
    @pytest.mark.asyncio
    async def test_get_products_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        query.count.return_value = 1

        # Diccionario simulado que representa un registro de producto en la base de datos.
        mock_row = (
            {
                "product_id": "PROD_001",
                "product_category": "Electronic",
                "brand": "Sony",
                "sku": "001",
                "product_cost_usd": 54.90,
                "selling_price_usd": 71.60,
                "created_at": date(2026, 7, 24),
                "updated_at": date(2026, 9, 8),
            }
        ) 
        query.all.return_value = [mock_row]

        result = await get_products(skip=0, limit=100, db=db)

        # Aserciones sobre los elementos de la respuesta paginada y sus tipos de datos.
        assert result is not None
        
        first_item = result["items"]
        assert first_item[0] == mock_row
        assert first_item[0]["product_id"] == "PROD_001"
        assert first_item[0]["product_category"] == "Electronic"
        assert first_item[0]["sku"] == "001"
        assert first_item[0]["product_cost_usd"] == 54.90
        assert first_item[0]["selling_price_usd"] == 71.60
        assert first_item[0]["created_at"] == date(2026, 7, 24)
        assert first_item[0]["updated_at"] == date(2026, 9, 8)


# Pruebas unitarias para la obtención de un producto individual por ID.
class TestProduct:
    # Valida que se lance un error HTTP 404 con el mensaje "Producto no encontrado" si el ID no existe.
    @pytest.mark.asyncio
    async def test_get_product_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos que la consulta no encuentra ningún producto en la BD.
        query.first.return_value = None
        query.one_or_none.return_value = None
        query.all.return_value = []

        # Capturamos la excepción esperada de FastAPI.
        with pytest.raises(HTTPException) as error:
                
            await get_product(
                        db=db,
                        product_id=None
            )
        
        assert error.value.status_code == 404
        assert error.value.detail == "Producto no encontrado"

    # Valida la obtención exitosa de un producto y la conversión de sus objetos date a formato string ISO.
    @pytest.mark.asyncio
    async def test_get_brands_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query

        # Creamos un objeto simulado (Mock) del modelo Producto con sus atributos.
        mock_product = MagicMock()
        mock_product.product_id = "PROD_001"
        mock_product.product_category = "Electronic"
        mock_product.brand = "Sony"
        mock_product.sku = "001"
        mock_product.product_cost_usd = 54.90
        mock_product.selling_price_usd = 71.60
        mock_product.created_at = date(2026, 7, 24)
        mock_product.updated_at = date(2026, 9, 8)
        query.first.return_value = mock_product

        result = await get_product(product_id="PROD_001", db=db)

        # Verificamos que los datos devueltos coincidan y que las fechas hayan sido serializadas a texto.
        assert result is not None
        
        assert result["product_id"] == "PROD_001"
        assert result["product_category"] == "Electronic"
        assert result["sku"] == "001"
        assert result["product_cost_usd"] == 54.90
        assert result["selling_price_usd"] == 71.60
        assert result["created_at"] == "2026-07-24"
        assert result["updated_at"] == "2026-09-08"


# Pruebas unitarias para el endpoint de obtención de categorías.
class TestCategories:
    # Comprueba que la consulta simple de categorías no ejecute la cláusula .filter().
    @pytest.mark.asyncio
    async def test_get_categories_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.first.return_value = None

        await get_categories(
                db=db
        )
        
        query.filter.assert_not_called()

    # Valida la ejecución y retorno correcto de la lista de categorías.
    @pytest.mark.asyncio
    async def test_get_categories_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query

        result = await get_categories(
                db=db
        )
        
        assert result is not None


# Pruebas unitarias para el endpoint de obtención de marcas (brands).
class TestBrands:
    # Comprueba que la consulta básica de marcas no aplique filtros innecesarios.
    @pytest.mark.asyncio
    async def test_get_brands_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.first.return_value = None

        await get_brands(
                db=db
        )
        
        query.filter.assert_not_called()

    # Valida que la respuesta del listado de marcas devuelva un resultado válido.
    @pytest.mark.asyncio
    async def test_get_brands_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query

        result = await get_brands(
                db=db
        )
        
        assert result is not None