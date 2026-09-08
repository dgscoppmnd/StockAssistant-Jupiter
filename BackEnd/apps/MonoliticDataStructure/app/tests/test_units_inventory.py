# Importamos los cinco endpoints que vamos a probar.
from src.api.routes.inventory import (
    get_inventory,
    get_critical_stock,
    get_overstock,
    get_warehouse_summary,
    get_product_inventory
)

# pytest permite crear y ejecutar las pruebas.
import pytest

# MagicMock sirve para crear objetos simulados.
# Lo utilizamos para simular la base de datos y las consultas
# sin tener que conectarnos realmente a PostgreSQL.
from unittest.mock import MagicMock

# HTTPException es la excepción que utilizan los endpoints
# cuando tienen que devolver errores HTTP, como un 404.
from fastapi import HTTPException



class TestRoot:

    # Probamos que get_inventory() funciona correctamente
    # cuando no se proporciona ningún filtro.
    @pytest.mark.asyncio
    async def test_get_inventory(self):

        # Creamos una base de datos y una consulta falsas.
        # db representa la sesión de SQLAlchemy y query representa
        # la consulta que normalmente haríamos a la base de datos.
        db = MagicMock()
        query = MagicMock()

        # Cuando el endpoint haga db.query(...), queremos que
        # utilice nuestra consulta simulada.
        db.query.return_value = query

        # Simulamos el comportamiento de paginate().
        # count() indica cuántos elementos existen.
        query.count.return_value = 0

        # offset() y limit() devuelven la misma consulta para
        # poder encadenar las operaciones.
        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos que la consulta no devuelve ningún registro.
        query.all.return_value = []

        # Ejecutamos el endpoint directamente.
        # Pasamos skip y limit manualmente porque estamos llamando
        # a la función directamente y no a través de FastAPI.
        result = await get_inventory(
            skip=0,
            limit=100,
            db=db
        )

        # El endpoint debe devolver algún resultado.
        assert result is not None

        # Comprobamos que se hizo una consulta a la base de datos.
        db.query.assert_called_once()


    # Comprobamos que se aplica correctamente el filtro
    # cuando se proporciona un warehouse_id.
    @pytest.mark.asyncio
    async def test_get_inventory_warehouse(self):

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query

        # Como el endpoint utiliza .filter(), debemos simularlo.
        # Devolvemos query para poder continuar con la paginación.
        query.filter.return_value = query

        query.count.return_value = 0
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        # Enviamos un almacén concreto para comprobar
        # que entra en la condición "if warehouse_id".
        result = await get_inventory(
            warehouse_id="warehouse-1",
            skip=0,
            limit=100,
            db=db
        )

        assert result is not None

        # Verificamos que filter() fue utilizado.
        query.filter.assert_called_once()


    # Comprobamos el filtro por product_id.
    @pytest.mark.asyncio
    async def test_get_inventory_product(self):

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query

        # El endpoint aplicará filter() al recibir product_id.
        query.filter.return_value = query

        query.count.return_value = 0
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        result = await get_inventory(
            product_id="product-1",
            skip=0,
            limit=100,
            db=db
        )

        assert result is not None
        query.filter.assert_called_once()


    # Comprobamos el filtro que selecciona productos
    # cuyo stock sea mayor o igual al mínimo indicado.
    @pytest.mark.asyncio
    async def test_get_inventory_min_stock(self):

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query

        query.filter.return_value = query
        query.count.return_value = 0
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        result = await get_inventory(
            min_stock=3,
            skip=0,
            limit=100,
            db=db
        )

        assert result is not None
        query.filter.assert_called_once()


    # Comprobamos el filtro que selecciona productos
    # cuyo stock sea menor o igual al máximo indicado.
    @pytest.mark.asyncio
    async def test_get_inventory_max_stock(self):

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query

        query.filter.return_value = query
        query.count.return_value = 0
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        result = await get_inventory(
            max_stock=3,
            skip=0,
            limit=100,
            db=db
        )

        assert result is not None
        query.filter.assert_called_once()


    # Comprobamos el filtro critical_only.
    # Cuando es True, el endpoint busca productos cuyo
    # current_stock sea inferior al reorder_level.
    @pytest.mark.asyncio
    async def test_get_inventory_critical_only(self):

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query

        query.filter.return_value = query
        query.count.return_value = 0
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        result = await get_inventory(
            critical_only=True,
            skip=0,
            limit=100,
            db=db
        )

        assert result is not None
        query.filter.assert_called_once()



class TestCritical:

    # Comprobamos que el endpoint devuelve una lista vacía
    # cuando no existen productos con stock crítico.
    @pytest.mark.asyncio
    async def test_critical_stock(self):

        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query

        # get_critical_stock() utiliza dos JOIN:
        # Inventory -> Product -> Warehouse.
        # Simulamos los JOIN devolviendo la misma consulta.
        query.join.return_value = query

        # También se aplica un filtro para comprobar
        # current_stock < reorder_level.
        query.filter.return_value = query

        # Simulamos que no existen resultados.
        query.all.return_value = []

        result = await get_critical_stock(db=db)

        # El resultado esperado es una lista vacía.
        assert result == []

        # Comprobamos las operaciones principales realizadas.
        db.query.assert_called_once()
        query.filter.assert_called_once()
        query.all.assert_called_once()



class TestOverstock:

    # Comprobamos el caso en el que no existen productos
    # con exceso de stock.
    @pytest.mark.asyncio
    async def test_overstock(self):

        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query

        # El endpoint realiza JOIN con Product y Warehouse.
        query.join.return_value = query

        # Se aplica el filtro de exceso de stock.
        query.filter.return_value = query

        query.all.return_value = []

        result = await get_overstock(db=db)

        assert result == []

        db.query.assert_called_once()
        query.filter.assert_called_once()
        query.all.assert_called_once()


    # Comprobamos un caso en el que sí existe un producto
    # con exceso de stock.
    @pytest.mark.asyncio
    async def test_get_overstock_with_product(self):

        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.join.return_value = query
        query.filter.return_value = query

        # Creamos un inventario falso con:
        # stock actual = 100
        # nivel de reorden = 20
        #
        # Como 100 > 20 * 2, este producto debe aparecer
        # como producto con exceso de stock.
        inventory = MagicMock()
        inventory.product_id = "product-1"
        inventory.current_stock = 100
        inventory.reorder_level = 20
        inventory.warehouse_id = "warehouse-1"
        inventory.overstock_risk = "high"

        # Información falsa del producto.
        product = MagicMock()
        product.product_category = "Electronics"
        product.brand = "Apple"

        # Información falsa del almacén.
        warehouse = MagicMock()
        warehouse.warehouse_location = "Madrid"

        # Simulamos el resultado de la consulta.
        # El endpoint espera recibir una tupla:
        # (inventario, producto, almacén).
        query.all.return_value = [
            (inventory, product, warehouse)
        ]

        result = await get_overstock(db=db)

        # Solo esperamos un producto.
        assert len(result) == 1

        # Comprobamos que los datos se han transformado
        # correctamente al diccionario que devuelve el endpoint.
        assert result[0]["product_id"] == "product-1"
        assert result[0]["product_category"] == "Electronics"
        assert result[0]["brand"] == "Apple"
        assert result[0]["current_stock"] == 100
        assert result[0]["reorder_level"] == 20
        assert result[0]["warehouse_id"] == "warehouse-1"
        assert result[0]["warehouse_location"] == "Madrid"

        # El endpoint calcula:
        # current_stock - reorder_level
        # 100 - 20 = 80
        assert result[0]["stock_excess"] == 80

        assert result[0]["overstock_risk"] == "high"




class TestWarehouseSummary:

    # Comprobamos que el resumen de un almacén
    # se calcula correctamente.
    @pytest.mark.asyncio
    async def test_get_warehouse_summary(self):

        db = MagicMock()

        # Creamos los datos simulados del almacén.
        warehouse = MagicMock()
        warehouse.warehouse_location = "Madrid"
        warehouse.storage_capacity = 1000
        warehouse.utilization_rate = 0.5

        # Creamos un producto de inventario para ese almacén.
        item = MagicMock()
        item.current_stock = 50
        item.inventory_turnover = 2
        item.reorder_level = 20

        # Primera consulta:
        # busca el almacén mediante warehouse_id.
        warehouse_query = MagicMock()
        warehouse_query.filter.return_value = warehouse_query
        warehouse_query.first.return_value = warehouse

        # Segunda consulta:
        # busca todos los elementos de inventario del almacén.
        inventory_query = MagicMock()
        inventory_query.filter.return_value = inventory_query
        inventory_query.all.return_value = [item]

        # El endpoint hace dos llamadas a db.query().
        #
        # Primera llamada -> warehouse_query
        # Segunda llamada -> inventory_query
        #
        # side_effect permite devolver un resultado diferente
        # en cada llamada.
        db.query.side_effect = [
            warehouse_query,
            inventory_query
        ]

        result = await get_warehouse_summary(
            warehouse_id="warehouse-1",
            db=db
        )

        # Comprobamos la información del almacén.
        assert result["warehouse_id"] == "warehouse-1"
        assert result["warehouse_location"] == "Madrid"
        assert result["storage_capacity"] == 1000
        assert result["utilization_rate"] == 0.5

        # Comprobamos los cálculos del inventario.
        #
        # Hay un único producto.
        assert result["total_products"] == 1

        # Su stock es 50.
        assert result["total_stock"] == 50

        # Su inventory_turnover es 2,
        # por lo que la media también es 2.
        assert result["avg_turnover"] == 2

        # 50 no es menor que 20,
        # por lo que no es un producto crítico.
        assert result["critical_items"] == 0

        # 50 sí es mayor que 20 * 2,
        # por lo que existe un producto con exceso.
        assert result["overstock_items"] != 0


    # Comprobamos que se devuelve un error 404
    # cuando el almacén solicitado no existe.
    @pytest.mark.asyncio
    async def test_get_warehouse_summary_not_found(self):

        db = MagicMock()
        query = MagicMock()

        query.filter.return_value = query

        # first() devuelve None para simular
        # que no se encontró ningún almacén.
        query.first.return_value = None

        db.query.return_value = query

        # Esperamos que el endpoint lance HTTPException.
        with pytest.raises(HTTPException) as error:

            await get_warehouse_summary(
                warehouse_id="warehouse-1",
                db=db
            )

        # El endpoint debe devolver un error 404.
        assert error.value.status_code == 404




class TestProductInventory:

    # Comprobamos que podemos obtener el inventario
    # de un producto en los almacenes.
    @pytest.mark.asyncio
    async def test_get_product_inventory(self):

        db = MagicMock()

        # Datos simulados del producto.
        product = MagicMock()
        product.product_category = "Electronics"
        product.brand = "Apple"

        # Datos simulados del inventario.
        inventory = MagicMock()
        inventory.warehouse_id = "warehouse-1"
        inventory.current_stock = 50
        inventory.reorder_level = 20
        inventory.safety_stock = 10
        inventory.stockout_risk = "low"
        inventory.inventory_turnover = 2

        # Datos simulados del almacén.
        warehouse = MagicMock()
        warehouse.warehouse_location = "Madrid"

        # ----------------------------------------------------
        # Primera consulta: buscar el producto.
        # ----------------------------------------------------
        product_query = MagicMock()

        product_query.filter.return_value = product_query

        # Simulamos que el producto existe.
        product_query.first.return_value = product

        # ----------------------------------------------------
        # Segunda consulta: buscar el inventario del producto.
        # ----------------------------------------------------
        inventory_query = MagicMock()

        # El endpoint hace un JOIN con Warehouse.
        inventory_query.join.return_value = inventory_query

        inventory_query.filter.return_value = inventory_query

        # La consulta devuelve el inventario junto con el almacén.
        inventory_query.all.return_value = [
            (inventory, warehouse)
        ]

        # Como el endpoint realiza dos db.query(),
        # utilizamos side_effect para indicar qué consulta
        # debe devolverse en cada llamada.
        db.query.side_effect = [
            product_query,
            inventory_query
        ]

        result = await get_product_inventory(
            product_id="product-1",
            db=db
        )

        # Comprobamos los datos principales del producto.
        assert result["product_id"] == "product-1"
        assert result["product_category"] == "Electronics"
        assert result["brand"] == "Apple"

        # El producto tiene 50 unidades en total.
        assert result["total_stock"] == 50

        # Comprobamos que existe una única ubicación.
        assert len(result["locations"]) == 1

        # Comprobamos los datos de esa ubicación.
        assert result["locations"][0]["warehouse_id"] == "warehouse-1"
        assert result["locations"][0]["warehouse_location"] == "Madrid"
        assert result["locations"][0]["current_stock"] == 50


    # Comprobamos el comportamiento cuando el producto
    # que buscamos no existe.
    @pytest.mark.asyncio
    async def test_get_product_inventory_not_found(self):

        db = MagicMock()
        query = MagicMock()

        query.filter.return_value = query

        # None significa que no se ha encontrado el producto.
        query.first.return_value = None

        db.query.return_value = query

        # Esperamos que el endpoint lance una excepción HTTP.
        with pytest.raises(HTTPException) as error:

            await get_product_inventory(
                product_id="product-1",
                db=db
            )

        # Comprobamos que el código de error es 404.
        assert error.value.status_code == 404

