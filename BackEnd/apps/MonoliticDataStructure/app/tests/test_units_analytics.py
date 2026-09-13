# Importamos Decimal para trabajar con precisión numérica en valores monetarios mockeados.
from decimal import Decimal

# Importamos las funciones de analítica que se van a someter a pruebas unitarias.
from src.api.routes.analytics import (
    get_product_performance,
    get_risk_analysis,
    get_inventory_optimization,
    _get_optimization_recommendation,

)

# pytest permite definir y ejecutar las pruebas unitarias asíncronas.
import pytest

# MagicMock permite simular la interfaz de SQLAlchemy (sesión y consultas) sin conectarse a la base de datos real.
from unittest.mock import MagicMock


# Conjunto de pruebas para el endpoint/función de rendimiento de productos.
class TestProductPerformance:
    # Prueba unitaria para verificar el comportamiento cuando no se proporciona un filtro de categoría.
    @pytest.mark.asyncio
    async def test_get_product_performance_without_category(self):
        # Inicializamos los objetos simulados para la base de datos y la consulta.
        db = MagicMock()
        query = MagicMock()
        
        # Configuramos el encadenamiento de métodos del QueryBuilder de SQLAlchemy.
        db.query.return_value = query
        query.join.return_value = query

        query.offset.return_value = query
        query.limit.return_value = query

        # Simulamos que la consulta no devuelve registros.
        query.all.return_value = []

        # Ejecutamos la función asíncrona pasando category=None.
        await get_product_performance(
            category=None,
            db=db,
            limit=100
        )

        # Verificamos que al no haber categoría no se haya aplicado ningún filtro SQL (.filter()).
        query.filter.assert_not_called()

    # Prueba unitaria que valida la transformación de datos y conversión de tipos cuando la consulta retorna resultados.
    @pytest.mark.asyncio
    async def test_get_product_performance_with_data(self):
        db = MagicMock()
        query = MagicMock()
        
        # Simulamos el flujo completo de encadenamiento del ORM para consultas agregadas.
        db.query.return_value = query
        query.join.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query

        # Fila ficticia devuelta por la base de datos con tipos Decimal típicos de columnas numéricas.
        mock_row = (
            "PROD-001", "Electronics", "Sony", 10,
            Decimal("50.0"), Decimal("1000.50"), Decimal("200.25"),
            Decimal("20.025"), Decimal("85.5"), Decimal("12.0")
        )
        query.all.return_value = [mock_row]

        # Invocamos la función enviando una categoría específica.
        result = await get_product_performance(
            category="Electronics",
            db=db,
            limit=100
        )

        # Aserciones sobre la estructura de la respuesta y conversión explícita de Decimal a float.
        assert result is not None
        assert len(result) == 1
        assert result[0]["product_id"] == "PROD-001"
        assert result[0]["total_revenue"] == 1000.50
        assert isinstance(result[0]["total_revenue"], float)
        assert result[0]["avg_risk_score"] == 12.0
        
        # Confirmamos que esta vez sí se aplicó la cláusula .filter() para la categoría.
        query.filter.assert_called_once()

    # Prueba para validar las relaciones (JOINs) y la cláusula de límite en la consulta SQL.
    @pytest.mark.asyncio
    async def test_get_product_performance_joins_and_limits(self):
        """4. Verificación de llamadas a JOINs y LIMIT con los argumentos correctos"""
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.join.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        # Ejecutamos con un límite personalizado de 25 registros.
        await get_product_performance(limit=25, db=db)

        # Verificamos que se hayan realizado exactamente dos JOINs en la consulta.
        assert query.join.call_count == 2
        
        # Comprobamos que el límite establecido fue pasado correctamente al ORM.
        query.limit.assert_called_once_with(25)


# Conjunto de pruebas para el análisis de riesgos de inventario y proveedores.
class TestRiskAnalysis:
    # Prueba de ejecución básica para get_risk_analysis cuando la BD no retorna datos.
    @pytest.mark.asyncio
    async def test_get_risk_analysis(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.join.return_value = query

        query.offset.return_value = query
        query.limit.return_value = query

        query.all.return_value = []

        await get_risk_analysis(
            db=db
        )

        # Aseguramos que los filtros de riesgo predeterminados siempre se evalúen.
        query.filter.assert_called()

    # Prueba de mapeo para productos con riesgo alto de rotura de stock (Stockout).
    @pytest.mark.asyncio
    async def test_get_risk_analysis_with_high_risk_stockout(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.join.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query

        # Fila simulada de un producto con nivel de reorden superior al stock actual.
        mock_row = ("PROD-001", "Electronics", "Sony", 10, 50, "HIGH")
    

        query.all.return_value = [mock_row]

        result = await get_risk_analysis(db=db)

        # Validamos que el resultado contenga la clave esperada y sus atributos estén bien mapeados.
        assert result is not None
        assert "high_stockout_risk_products" in result
        assert len(result["high_stockout_risk_products"]) == 1
        
        stockout_product = result["high_stockout_risk_products"][0]
        assert stockout_product["product_id"] == "PROD-001"
        assert stockout_product["product_category"] == "Electronics"
        assert stockout_product["brand"] == "Sony"
        assert stockout_product["current_stock"] == 10
        assert stockout_product["reorder_level"] == 50
        assert stockout_product["stockout_risk"] == "HIGH"

    # Prueba compleja usando side_effect para simular las 3 consultas secuenciales que realiza la función.
    @pytest.mark.asyncio
    async def test_get_risk_analysis_with_high_risk_suppliers(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.join.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.having.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query

        # Definimos respuestas distintas para cada una de las 3 llamadas consecutivas a query.all().
        stockout_data = [("PROD-001", "Electronics", "Sony", 10, 50, "HIGH")]
        operational_data = [("PROD-001", "Electronics", "Sony", 10)]
        supplier_data = [("SUP-001", 1, 10, 85.5)]

        # side_effect devuelve cada lista secuencialmente en las llamadas 1, 2 y 3 respectivamente.
        query.all.side_effect = [stockout_data, operational_data, supplier_data]

        result = await get_risk_analysis(db=db)

        # Validaciones principales de existencia de las tres secciones de riesgo en la respuesta.
        assert result is not None
        assert len(result["high_stockout_risk_products"]) == 1
        assert len(result["high_operational_risk_products"]) == 1
        assert len(result["high_risk_suppliers"]) == 1

        # Validación del bloque de riesgo de desabastecimiento.
        high_stockout_risk_product = result["high_stockout_risk_products"][0]
        assert high_stockout_risk_product["product_id"] == "PROD-001"
        assert high_stockout_risk_product["product_category"] == "Electronics"
        assert high_stockout_risk_product["brand"] == "Sony"
        assert high_stockout_risk_product["current_stock"] == 10
        assert high_stockout_risk_product["reorder_level"] == 50
        assert high_stockout_risk_product["stockout_risk"] == "HIGH"

        # Validación del bloque de riesgo operacional.
        high_operational_risk_products = result["high_operational_risk_products"][0]
        assert high_operational_risk_products["product_id"] == "PROD-001"
        assert high_operational_risk_products["product_category"] == "Electronics"
        assert high_operational_risk_products["brand"] == "Sony"
        assert high_operational_risk_products["operational_risk_score"] == 10

        # Validación del bloque de riesgo de proveedores.
        high_risk_suppliers = result["high_risk_suppliers"][0]
        assert high_risk_suppliers["supplier_id"] == "SUP-001"
        assert high_risk_suppliers["supplier_rating"] == 1
        assert high_risk_suppliers["supplier_performance_score"] == 10
        assert high_risk_suppliers["avg_disruption_risk"] == 85.5
        
        
# Conjunto de pruebas para las métricas de optimización de inventario.
class TestInventoryOptimization:
    # Caso base sin registros en la base de datos.
    @pytest.mark.asyncio
    async def test_get_inventory_optimization(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.join.return_value = query

        query.offset.return_value = query
        query.limit.return_value = query

        query.all.return_value = []

        await get_inventory_optimization(
            db=db,

        )

        query.filter.assert_called()

    # Caso con retorno de datos para validar el mapeo de campos de optimización y stock de seguridad.
    @pytest.mark.asyncio
    async def test_get_inventory_optimization_with_data(self):
        db = MagicMock()
        query = MagicMock()
        
        db.query.return_value = query
        query.join.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query

        # Fila simulada con identificadores, stock, niveles de reorden y puntuaciones de riesgo.
        mock_row = ("PROD-001", "Electronics", "Sony", 10, 1, 8, 0.9, 9, 7)
    

        query.all.return_value = [mock_row]

        result = await get_inventory_optimization(db=db)
        assert result is not None
        assert len(result) == 1

        # Verificación detallada campo por campo.
        first_item=result[0]
        assert first_item["product_id"] == "PROD-001"
        assert first_item["product_category"] == "Electronics"
        assert first_item["brand"] == "Sony"
        assert first_item["current_stock"] == 10
        assert first_item["reorder_level"] == 1
        assert first_item["safety_stock"] == 8
        assert first_item["optimization_score"] == 0.9
        assert first_item["stockout_risk"] == 9
        assert first_item["overstock_risk"] == 7


# Pruebas unitarias directas sobre la lógica condicional del helper de recomendaciones.
class TestOptimizationRecommendation:
    @pytest.mark.asyncio
    async def test_get_optimization_recommendation(self):
        
        # Evaluación cuando la puntuación global es baja (< 30) sin superar umbrales específicos.
        result = _get_optimization_recommendation(29, 69, 69)
        assert result is not None
        assert result == "📊 Revisar política de inventario"

        # Evaluación cuando el riesgo de stockout es alto (> 70).
        result = _get_optimization_recommendation(29, 71, 69)
        assert result is not None
        assert result == "⚠️ Aumentar stock críticamente bajo"

        # Evaluación cuando el riesgo de sobrestock es alto (> 70).
        result = _get_optimization_recommendation(29, 69, 71)
        assert result is not None
        assert result == "⚠️ Reducir exceso de inventario"

        # Evaluación para puntuaciones intermedias (entre 30 y 50).
        result = _get_optimization_recommendation(49, 69, 69)
        assert result is not None
        assert result == "📈 Mejorar eficiencia de inventario"

        # Evaluación para puntuaciones óptimas (> 50).
        result = _get_optimization_recommendation(51, 69, 69)
        assert result is not None
        assert result == "✅ Optimización adecuada"