from datetime import date

# Importamos HTTPException para verificar el manejo de errores HTTP.
from fastapi import HTTPException

# Importamos las funciones de las rutas de métricas que vamos a probar.
from src.api.routes.metrics import (
    get_metrics,
    get_product_metrics,
    get_metrics_summary

)

# pytest permite definir y ejecutar las pruebas unitarias asíncronas.
import pytest

# MagicMock sirve para crear objetos simulados.
# Lo utilizamos para simular la base de datos y las consultas
# sin tener que conectarnos realmente a PostgreSQL.
from unittest.mock import MagicMock


# Pruebas para el endpoint de obtención general de métricas.
class TestMetrics:
    # Valida el comportamiento de get_metrics cuando no se pasan filtros de búsqueda.
    @pytest.mark.asyncio
    async def test_get_product_performance_with_none(self):
        # Inicializamos los objetos simulados para la base de datos y la consulta.
        db = MagicMock()
        query = MagicMock()

        # Configuramos el encadenamiento de métodos del ORM de SQLAlchemy.
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos que no hay registros en la base de datos.
        query.count.return_value = 0 
        query.all.return_value = []

        # Ejecutamos la función con parámetros nulos/por defecto.
        await get_metrics(
            skip=0,
            db=db,
            limit=100,
            product_id=None,
            start_date=None,
            end_date=None
        )

        # Verificamos que no se haya llamado a .filter() ya que no se enviaron criterios de búsqueda.
        query.filter.assert_not_called()

    # Valida que get_metrics retorne correctamente los elementos paginados cuando existen datos.
    @pytest.mark.asyncio
    async def test_get_product_performance_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        query.count.return_value = 0 
        # Fila de datos simulada con fechas en formato string.
        mock_row = ("PROD_001", "07/09/2026", "10/09/2026") 
        query.all.return_value = [mock_row]

        result = await get_metrics(skip=0, limit=100, db=db)

        # Aserciones sobre el resultado obtenido y el primer elemento paginado.
        assert result is not None
       
        first_item = result["items"][0]
        assert first_item == mock_row
        assert first_item[0] == "PROD_001"
        assert first_item[1] == "07/09/2026"
        assert first_item[2] == "10/09/2026"


# Pruebas unitarias para las métricas detalladas de un producto específico.
class TestProductMetrics:
    # Valida que se lance una excepción HTTP 404 si el producto solicitado no existe en la BD.
    @pytest.mark.asyncio
    async def test_get_product_metrics_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        # Simulamos que la consulta no devuelve ningún producto.
        query.first.return_value = None

        # Esperamos que la función lance una excepción HTTPException de FastAPI.
        with pytest.raises(HTTPException) as error:
        
            await get_product_metrics(
                        days=90,
                        db=db,
                        product_id=None
            )
        
        # Verificamos que el código de estado sea 404 Not Found y el mensaje sea el adecuado.
        assert error.value.status_code == 404
        assert error.value.detail == "Producto no encontrado"

    # Valida el cálculo del desglose diario y los promedios/resumen cuando el producto sí existe.
    @pytest.mark.asyncio
    async def test_get_product_metrics_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query

        # Creamos un objeto simulado para representar la entidad Producto.
        mock_product = MagicMock()
        mock_product.product_category = "Electronics"
        mock_product.brand = "Sony"
        query.first.return_value = mock_product

        # Creamos un objeto simulado para representar una fila de métricas del producto.
        mock_metric = MagicMock()
        mock_metric.date = date(2026, 9, 7)  
        mock_metric.inventory_optimization_score = 0.65
        mock_metric.supplier_performance_score = 0.70
        mock_metric.supply_chain_efficiency = 10.0
        mock_metric.sustainability_score = 0.88
        mock_metric.operational_risk_score = 0.90

        query.all.return_value = [mock_metric]
        
        # Ejecutamos la consulta para un rango de 70 días y un producto específico.
        result = await get_product_metrics(
                        days=70,
                        db=db,
                        product_id="PROD_001"
        )
        
        assert result is not None
        
        # Verificamos los metadatos generales devueltos en la respuesta.
        assert result["product_id"] == "PROD_001"
        assert result["product_category"] == "Electronics"
        assert result["brand"] == "Sony"
        assert result["period_days"] == 70

        # Verificamos el formateo de las métricas históricas (lista de métricas formateadas a ISO/String).
        assert len(result["metrics"]) == 1
        assert result["metrics"][0] == {
            "date": "2026-09-07",
            "inventory_optimization_score": 0.65,
            "supplier_performance_score": 0.70,
            "supply_chain_efficiency": 10.0,
            "sustainability_score": 0.88,
            "operational_risk_score": 0.90,
        }

        # Verificamos los cálculos de promedios generados en la sección "summary".
        assert result["summary"] == {
            "avg_inventory_optimization": 0.65,
            "avg_supplier_performance": 0.70,
            "avg_supply_chain_efficiency": 10.0,
            "avg_sustainability": 0.88,
            "avg_operational_risk": 0.90,
        }


# Pruebas unitarias para el endpoint del resumen global o agrupado por categoría de métricas.
class TestMetricSummary:
    # Comprueba que no se aplique filtro por categoría si este parámetro es None.
    @pytest.mark.asyncio
    async def test_get_metrics_summary_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.first.return_value = None

        await get_metrics_summary(
                db=db,
                category=None
        )
        
        # Confirmamos que la consulta no ejecutó un .filter() innecesario.
        query.filter.assert_not_called()

    # Comprueba la estructuración del resumen métrico agrupado para una categoría específica.
    @pytest.mark.asyncio
    async def test_get_product_metrics_with_values(self):
        db = MagicMock()
        query = MagicMock()

        # Simulamos la cadena de llamadas del ORM incluyendo JOINs y GROUP BY.
        db.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.group_by.return_value = query
        query.join.return_value = query

        # Tupla simulada recibida desde la consulta SQL agrupadora (func.avg, func.count).
        mock_row = ("Electronic", 0.14, 0.22, 0.6, 0.5, 0.9, 1)
        query.all.return_value = [mock_row]
                
        result = await get_metrics_summary(
                        db=db,
                        category="Electronic"
                )
        
        # Validamos que el resultado mapee la tupla al diccionario esperado con las claves de promedios.
        assert result is not None
        assert result[0] == {
                    "category": "Electronic",
                    "avg_inventory_optimization": 0.14,
                    "avg_supplier_performance": 0.22,
                    "avg_supply_chain_efficiency": 0.6,
                    "avg_sustainability": 0.5,
                    "avg_operational_risk": 0.9,
                    "total_metrics": 1
                }