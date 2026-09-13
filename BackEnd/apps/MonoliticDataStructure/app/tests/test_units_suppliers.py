from datetime import date, datetime
from fastapi import HTTPException

# Modelos ORM y endpoints bajo prueba de la API de gestión de proveedores
from src.api.models import Supplier
from src.api.routes.suppliers import (
    get_supplier,
    get_supplier_efficiency,
    get_supplier_performance,
    get_suppliers
)

# Framework de pruebas asíncronas
import pytest

# Herramienta para simular objetos de SQLAlchemy (sesiones y consultas)
from unittest.mock import MagicMock


class TestSuppliers:
    """Pruebas para el endpoint de listado general de proveedores."""

    @pytest.mark.asyncio
    async def test_get_suppliers_with_none(self):
        # 1. Instanciación de mocks para la base de datos y la consulta
        db = MagicMock()
        query = MagicMock()

        # 2. Configuración del patrón builder de SQLAlchemy (métodos encadenados devuelven la misma consulta)
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # 3. Definición de resultados simulados para un listado vacío
        query.count.return_value = 0 
        query.all.return_value = []

        # 4. Ejecución del endpoint sin aplicar filtro por calificación mínima
        await get_suppliers(
            skip=0,
            limit=0,
            db=db,
            min_rating=None
        )

        # 5. Verificación: al no pasar 'min_rating', no debe aplicarse el método .filter()
        query.filter.assert_not_called()


    @pytest.mark.asyncio
    async def test_get_suppliers_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.count.return_value = 1

        # Fecha de referencia fija para garantizar determinismo en las validaciones
        test_date = datetime(2026, 9, 8, 10, 0, 0)

        # Instancia real del modelo ORM simulando la respuesta de la base de datos
        mock_supplier = Supplier(
            supplier_id="SUP_001",
            supplier_rating=4.50,
            lead_time_days=7,
            supplier_performance_score=92.50,
            sustainability_score=88.00,
            created_at=test_date,
            updated_at=test_date
        )

        # La consulta .all() devolverá una lista con la entidad simulada
        query.all.return_value = [mock_supplier]

        # Ejecución del endpoint aplicando filtro por nota mínima
        result = await get_suppliers(
            skip=0,
            limit=0,
            db=db,
            min_rating=0.5
        )

        # Comprobación de la estructura del diccionario devuelto
        assert result is not None
        assert "items" in result
        assert len(result["items"]) > 0

        # Acceso mediante claves de diccionario en lugar de atributos de objeto
        first_item = result["items"][0]
        assert first_item["supplier_id"] == "SUP_001"
        assert first_item["supplier_rating"] == 4.50
        assert first_item["lead_time_days"] == 7
        assert first_item["supplier_performance_score"] == 92.50
        assert first_item["sustainability_score"] == 88.00
        # Validación de la conversión implícita de objetos datetime a formato ISO 8601
        assert first_item["created_at"] == test_date.isoformat()
        assert first_item["updated_at"] == test_date.isoformat()



class TestSupplier:
    """Pruebas para la obtención del detalle de un único proveedor por ID."""

    @pytest.mark.asyncio
    async def test_get_supplier_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        # Simula que la búsqueda por ID no encontró ningún registro en la BD
        query.first.return_value = None
        query.one_or_none.return_value = None

        query.count.return_value = 0 
        query.all.return_value = []

        # Captura y validación de la excepción HTTP lanzada por el endpoint cuando no existe el proveedor
        with pytest.raises(HTTPException) as error:
            await get_supplier(
                db=db,
                supplier_id=None
            )

        # Confirmación del código de estado 404 (Not Found) y su mensaje descriptivo
        assert error.value.status_code == 404
        assert error.value.detail == "Proveedor no encontrado"


    @pytest.mark.asyncio
    async def test_get_supplier_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query

        test_date = datetime(2026, 9, 8, 10, 0, 0)
        
        mock_supplier = Supplier(
            supplier_id="SUP_001",
            supplier_rating=4.50,
            lead_time_days=7,
            supplier_performance_score=92.50,
            sustainability_score=88.00,
            created_at=test_date,
            updated_at=test_date
        )

        # .first() devuelve directamente el objeto ORM del proveedor encontrado
        query.first.return_value = mock_supplier

        result = await get_supplier(supplier_id="PROD_001", db=db)

        assert result is not None
        
        # En este endpoint se evalúa directamente el objeto ORM (acceso por atributos con punto)
        assert result.supplier_id == "SUP_001"
        assert result.supplier_rating == 4.50
        assert result.lead_time_days == 7
        assert result.supplier_performance_score == 92.50
        assert result.sustainability_score == 88.00
        assert result.created_at == test_date
        assert result.updated_at == test_date



class TestSupplierEfficiency:
    """Pruebas para el cálculo de eficiencia agregada de proveedores."""

    @pytest.mark.asyncio
    async def test_get_supplier_efficiency_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        query.count.return_value = 0 
        query.all.return_value = []

        await get_supplier_efficiency(
            db=db,
            min_rating=None
        )

        # Garantiza que sin min_rating la consulta no añade filtro SQL adicional
        query.filter.assert_not_called()


    @pytest.mark.asyncio
    async def test_get_supplier_efficiency_with_values(self):
        db = MagicMock()
        query = MagicMock()

        # Configuración de los métodos de agregación y uniones SQL
        db.query.return_value = query
        query.filter.return_value = query
        query.join.return_value = query
        query.outerjoin.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Tupla que representa una fila de resultados agregados (AVG, COUNT, JOINs)
        mock_supplier = ("SUP_001", 4.50, 92.50, 88.00, 80.00, 7.5, 20)

        query.all.return_value = [mock_supplier]

        result = await get_supplier_efficiency(
            db=db,
            min_rating=0.5
        )

        assert result is not None
        assert len(result) > 0

        # Verificación de que la tupla de agregación SQL se mapeó correctamente a claves de diccionario
        first_item = result[0]
        assert first_item["supplier_id"] == "SUP_001"
        assert first_item["supplier_rating"] == 4.50
        assert first_item["supplier_performance_score"] == 92.50
        assert first_item["sustainability_score"] == 88.00
        assert first_item["sustainability_score"] == 88.00
        assert first_item["avg_on_time_delivery"] == 80.00
        assert first_item["avg_delivery_days"] == 7.5
        assert first_item["products_supplied"] == 20



class TestSupplierPerformance:
    """Pruebas para las métricas detalladas de rendimiento logístico del proveedor."""

    @pytest.mark.asyncio
    async def test_get_supplier_performance_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.first.return_value = None
        query.one_or_none.return_value = None

        query.count.return_value = 0 
        query.all.return_value = []

        # Verificación de error 404 al intentar obtener performance de un proveedor inexistente
        with pytest.raises(HTTPException) as error:
            await get_supplier_performance(
                db=db,
                supplier_id=None
            )
                
        assert error.value.status_code == 404
        assert error.value.detail == "Proveedor no encontrado"


    @pytest.mark.asyncio
    async def test_get_supplier_performance_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query

        test_date = datetime(2026, 9, 8, 10, 0, 0)

        # 1. Entidad principal (Proveedor)
        mock_supplier = Supplier(
            supplier_id="SUP_001",
            supplier_rating=4.50,
            supplier_performance_score=92.50,
            sustainability_score=88.00,
            lead_time_days=7,
            created_at=test_date,
            updated_at=test_date
        )

        # 2. Tupla de promedios calculados para la segunda consulta de logística
        mock_logistics = (10.5, 11.4, 54.6, 15.6, 20)

        # 'side_effect' devuelve mock_supplier en la 1ª llamada a .first() y mock_logistics en la 2ª
        query.first.side_effect = [mock_supplier, mock_logistics]

        result = await get_supplier_performance(supplier_id="PROD_001", db=db)

        assert result is not None

        # Validación del diccionario final que combina datos de la entidad y métricas anidadas
        assert result == {
            "supplier_id": "SUP_001",
            "supplier_rating": 4.50,
            "supplier_performance_score": 92.50,
            "sustainability_score": 88.00,
            "lead_time_days": 7,
            "performance_metrics": {
                "avg_on_time_delivery": 10.5,
                "avg_delivery_days": 11.4,
                "avg_shipping_cost": 54.6,
                "avg_disruption_risk": 15.6,
                "total_shipments": 20
            }
        }