from datetime import date
from fastapi import HTTPException

# Endpoints a evaluar pertenecientes a la API de gestión de ventas
from src.api.routes.sales import (
    get_sales,
    get_sales_trends,
    get_top_products,
    get_sales_summary
)

# pytest permite ejecutar pruebas unitarias asíncronas
import pytest

# MagicMock simula la sesión de base de datos y sus consultas de SQLAlchemy
from unittest.mock import MagicMock


class TestSales:
    """Pruebas unitarias para el endpoint principal de ventas (get_sales)."""

    @pytest.mark.asyncio
    async def test_get_sales_with_none(self):
        # Mocks para la sesión de BD y el constructor de consultas.
        db = MagicMock()
        query = MagicMock()

        # Configuración del encadenamiento de métodos de SQLAlchemy.
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query

        # Sin registros: la consulta retorna lista vacía
        query.count.return_value = 0 
        query.all.return_value = []

        await get_sales(
            skip=0,
            limit=0,
            db=db,
            product_id=None,
            start_date=None,
            end_date=None,
            year=None,
            quarter=None
        )

        # Confirma que al no enviar parámetros opcionales no se ejecuta .filter()
        query.filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_sales_with_values(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.count.return_value = 1

        # Tupla simulada que devuelve la base de datos
        mock_row = ("PROD_001", "2026-07-01", "2026-09-08", 2026, 2)
        query.all.return_value = [mock_row]
                
        result = await get_sales(
            skip=0,
            limit=0,
            db=db,
            product_id="PROD_001",
            start_date="2026-07-01",
            end_date="2026-09-08",
            year=2026,
            quarter=2
        )
        
        # Valida que el resultado transforme la tupla en los campos esperados
        assert result is not None
        first_item = result["items"][0]
        assert first_item == mock_row
        assert first_item[0] == "PROD_001"
        assert first_item[1] == "2026-07-01"
        assert first_item[2] == "2026-09-08"
        assert first_item[3] == 2026
        assert first_item[4] == 2


class TestSalesTrends:
    """Pruebas para las tendencias de ventas en el tiempo (get_sales_trends)."""

    @pytest.mark.asyncio
    async def test_get_sales_trends_with_none(self):
        db = MagicMock()
        query = MagicMock()
        
        # Mock secundario para aislar la llamada obligatoria del filtro de fecha
        query_after_date = MagicMock()

        db.query.return_value = query
        # El primer .filter() (fecha por defecto) retorna el mock secundario
        query.filter.return_value = query_after_date

        query.count.return_value = 0 
        query.all.return_value = []

        await get_sales_trends(
            db=db,
            product_id=None,
            days=30
        )

        # Garantiza que tras filtrar por fecha no se haya ejecutado filtro por product_id
        query_after_date.filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_sales_trends_with_values(self):
        db = MagicMock()
        query = MagicMock()
        
        # Habilita el encadenamiento para consultas con agrumapiento y orden
        db.query.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query

        mock_row = (date(2026,7,10), 10.0, 2.5, 4.8, 2)
        query.all.return_value = [mock_row]

        result = await get_sales_trends(
            db=db,
            product_id="PROD_001",
            days=30
        )

        # Valida el formateo ISO de la fecha y el mapeo de los totales
        assert result is not None
        assert len(result) > 0
        first_item = result[0]
        assert first_item["date"] == "2026-07-10"
        assert first_item["total_units"] == 10.0
        assert first_item["total_revenue"] == 2.5
        assert first_item["total_profit"] == 4.8
        assert first_item["num_transactions"] == 2


class TestSalesSummary:
    """Pruebas para los resúmenes y métricas agregadas (get_sales_summary)."""

    @pytest.mark.asyncio
    async def test_get_sales_summary_with_none(self):
        db = MagicMock()
        query = MagicMock()
        query_after_date = MagicMock()

        db.query.return_value = query
        query.filter.return_value = query_after_date

        query.count.return_value = 0 
        query.all.return_value = []

        await get_sales_summary(
            db=db,
            product_id=None,
            year=2026
        )

        # Asegura que no se aplique filtro opcional si product_id es None
        query_after_date.filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_sales_trends_with_values(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query

        # Tupla con los agregados acumulados devueltos por la BD
        mock_row = (100, 10.0, 2.5, 4.8, 2.9, 6.0)

        # Soporte para .first() o .all() según implemente el endpoint
        query.first.return_value = mock_row
        query.all.return_value = [mock_row]

        result = await get_sales_summary(
            db=db,
            product_id="PROD_001",
            year=2026
        )

        # Valida la construcción del diccionario de respuesta con promedios y totales
        assert result is not None
        assert len(result) > 0
        
        assert result["total_transactions"] == 100
        assert result["total_units_sold"] == 10.0
        assert result["total_revenue"] == 2.5
        assert result["total_profit"] == 4.8
        assert result["avg_profit_per_sale"] == 2.9
        assert result["avg_units_per_sale"] == 6.0


class TestTopProducts:
    """Pruebas para el ranking de productos más vendidos (get_top_products)."""

    @pytest.mark.asyncio
    async def test_get_top_products_with_none(self):
        db = MagicMock()
        query = MagicMock()

        db.query.return_value = query
        query.count.return_value = 0 
        query.all.return_value = []

        await get_top_products(
            db=db,
            limit=100,
            period=25
        )

        # Verifica que la consulta base no ejecute filtros adicionales
        query.filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_sales_trends_with_values(self):
        db = MagicMock()
        query = MagicMock()
        
        # Configuración completa para soportar JOINs, subconsultas y paginación
        db.query.return_value = query
        query.filter.return_value = query
        query.join.return_value = query          
        query.outerjoin.return_value = query    
        query.group_by.return_value = query
        query.having.return_value = query        
        query.order_by.return_value = query
        query.limit.return_value = query
        query.offset.return_value = query
        query.select_from.return_value = query

        mock_row = ("PROD_001", "Electronic", "Sony", 5.0, 3.2, 2.7, 2)
        query.all.return_value = [mock_row]

        result = await get_top_products(
            db=db,
            limit=100,
            period=25
        )

        # Valida que los datos del producto top se mapeen correctamente
        assert result is not None
        assert len(result) > 0
        first_item = result[0]
        assert first_item["product_id"] == "PROD_001"
        assert first_item["product_category"] == "Electronic"
        assert first_item["brand"] == "Sony"
        assert first_item["total_units_sold"] == 5.0
        assert first_item["total_revenue"] == 3.2
        assert first_item["total_profit"] == 2.7
        assert first_item["num_sales"] == 2