# Importamos los cuatro endpoints de logística que vamos a probar.
from src.api.routes.logistics import (
    get_logistics,
    get_logistics_summary,
    get_transport_modes,
    get_efficiency_metrics

)

# pytest permite crear y ejecutar las pruebas unitarias asíncronas.
import pytest

# MagicMock sirve para crear objetos simulados.
# Lo utilizamos para simular la base de datos y las consultas
# sin tener que conectarnos realmente a PostgreSQL.
from unittest.mock import MagicMock


# Pruebas unitarias para el endpoint principal de obtención de registros logísticos.
class TestLogistic:
    # Verifica el comportamiento cuando se consulta la lista sin aplicar filtros específicos.
    @pytest.mark.asyncio
    async def test_get_logistic_with_none(self):
        # Inicialización de mocks para la sesión de BD y la consulta SQLAlchemy.
        db = MagicMock()
        query = MagicMock()
        
        # Configuración del encadenamiento de la consulta ORM.
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos un total de 0 registros encontrados.
        query.count.return_value = 0  
        query.all.return_value = []

        # Ejecutamos la función con todos los parámetros opcionales en None.
        await get_logistics(
            skip=0,
            db=db,
            limit=100,
            product_id=None,
            supplier_id=None,
            transport_mode=None,
            warehouse_id=None
        )

        # Confirmamos que no se haya aplicado ninguna cláusula .filter() al no enviar parámetros de filtro.
        query.filter.assert_not_called()

    # Verifica la respuesta del endpoint cuando la consulta devuelve un registro logístico válido.
    @pytest.mark.asyncio
    async def test_get_logistic_with_value(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos que existe 1 registro en total.
        query.count.return_value = 1

        # Tupla simulada con la estructura del registro de logística devuelto por SQLAlchemy.
        mock_row = ("PROD_001", "SUP_001", "WAR_001", "TRANS_001") 
        query.all.return_value = [mock_row]
        
        # Ejecutamos la consulta paginada básica.
        result = await get_logistics(skip=0, limit=100, db=db)
        
        # Aserciones sobre la estructura devuelta en la paginación y sus campos.
        assert result is not None

        first_item = result["items"][0]
        assert first_item == mock_row
        assert first_item[0] == "PROD_001"
        assert first_item[1] == "SUP_001"
        assert first_item[2] == "WAR_001"
        assert first_item[3] == "TRANS_001"


# Pruebas unitarias para el endpoint de consulta de modos de transporte disponibles.
class TestTransportModes:
    # Comprueba la consulta básica de modos de transporte sin filtros aplicados.
    @pytest.mark.asyncio
    async def test_get_transport_modes_with_none(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query

        await get_transport_modes(db)

        # Asegura que no se apliquen filtros .filter() no requeridos.
        query.filter.assert_not_called()

    # Valida el formateo y extracción de los modos de transporte únicos obtenidos.
    @pytest.mark.asyncio
    async def test_get_transport_modes(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.distinct.return_value = query

        # Simulamos el retorno de tuplas individuales generadas por la cláusula distinct/select.
        query.all.return_value = [("Air",), ("Road",), ("Sea",)]

        result = await get_transport_modes(db=db)

        # Verificamos la desestructuración de las tuplas en una lista simple de strings.
        assert result is not None
        assert result == ["Air", "Road", "Sea"]

        # Confirmamos la ejecución estricta de las llamadas al ORM.
        db.query.assert_called_once()
        query.distinct.assert_called_once()
        query.all.assert_called_once()


# Pruebas unitarias para el endpoint de resumen métrico de logística.
class TestLogisticSummary:
    # Prueba la obtención del resumen general cuando no se pasa un proveedor específico.
    @pytest.mark.asyncio
    async def test_get_logistic_summary_with_none(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.filter.return_value = query

        result = await get_logistics_summary(supplier_id=None, db=db)
        assert result is not None

    # Valida el cálculo y mapeo a diccionario del resumen para un proveedor específico.
    @pytest.mark.asyncio
    async def test_get_logistic_summary_with_values(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.filter.return_value = query
        
        # Tupla con métricas agregadas (totales y promedios) retornada por func.avg/count.
        mock_tuple = (10, 14.88, 7.7, 4.6, 2.5, 6.4)
        query.first.return_value = mock_tuple

        result = await get_logistics_summary(supplier_id="SUP_001", db=db)

        # Diccionario esperado tras la conversión de la tupla SQL en el endpoint.
        expected_dict = {
            "total_shipments": 10,
            "avg_shipping_cost": 14.88,
            "avg_delivery_days": 7.7,
            "avg_on_time_delivery_rate": 4.6,
            "avg_supply_chain_efficiency": 2.5,
            "avg_supply_disruption_risk": 6.4,
        }

        assert result == expected_dict


# Pruebas unitarias para el endpoint de métricas de eficiencia por almacén.
class TestEffiencyMetrics:
    # Comprueba la respuesta cuando no hay registros para las métricas de eficiencia.
    @pytest.mark.asyncio
    async def test_get_efficiency_metrics_with_none(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.all.return_value = []

        result = await get_efficiency_metrics(warehouse_id=None, db=db)
        assert result is not None

    # Valida la transformación de tuplas agrupadas por modo de transporte a formato JSON/diccionario.
    @pytest.mark.asyncio
    async def test_get_efficiency_metrics_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query

        # Tupla agrupada por modo de transporte con métricas de costo y tiempo.
        mock_tuple = ("Air", 10, 14.88, 7.7, 4.6)
        
        query.all.return_value = [mock_tuple]

        result = await get_efficiency_metrics(warehouse_id="WAR_001", db=db)

        # Estructura de lista de diccionarios esperada en la respuesta final.
        expected_dict = [{
            "transportation_mode": "Air",
            "shipments": 10,
            "avg_shipping_cost": 14.88,
            "avg_delivery_days": 7.7,
            "avg_on_time_delivery": 4.6
        }]

        assert result == expected_dict