import sys
from pathlib import Path

_app_dir = Path(__file__).resolve().parent.parent
_src_dir = _app_dir / "src"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from fastapi.testclient import TestClient
import pytest

from src.api.main import app

client = TestClient(app)


def test_ml_health_endpoint():
    """Verifica el endpoint GET /api/v1/ml/health y la conectividad con MLflow."""
    response = client.get("/api/v1/ml/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["mlflow_connected"] is True
    assert "stockout-predictor" in data["models"]
    assert "reorder-forecaster" in data["models"]
    assert data["models"]["stockout-predictor"]["registered"] is True
    assert data["models"]["reorder-forecaster"]["registered"] is True
    assert "2" in data["models"]["stockout-predictor"]["production_versions"]
    assert "2" in data["models"]["reorder-forecaster"]["production_versions"]


def test_ml_stockout_prediction_real_product():
    """Verifica la inferencia de riesgo de rotura de stock con datos reales de PostgreSQL."""
    payload = {
        "product_id": "PRD0000001",
        "warehouse_id": "WH004",
    }
    response = client.post("/api/v1/ml/stockout", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["product_id"] == "PRD0000001"
    assert data["warehouse_id"] == "WH004"
    assert data["model_name"] == "stockout-predictor"
    assert data["model_stage"] == "Production"
    assert data["prediction"] in (0, 1)
    assert 0.0 <= data["probability"] <= 1.0
    assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(data["action_required"], bool)
    assert len(data["recommendation"]) > 15

    # Contexto operativo
    op = data["operational_context"]
    assert "current_stock" in op
    assert "reorder_level" in op
    assert "daily_demand" in op
    assert "stock_coverage_days" in op
    assert "product_name" in op
    assert "warehouse_location" in op

    # Features usadas
    features = data["features_used"]
    assert "stock_coverage_days" in features
    assert "daily_demand_rolling_mean_7" in features


def test_ml_reorder_prediction_real_product():
    """Verifica la inferencia de recomendación de compra con datos reales de PostgreSQL."""
    payload = {
        "product_id": "PRD0000001",
        "warehouse_id": "WH004",
    }
    response = client.post("/api/v1/ml/reorder", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["product_id"] == "PRD0000001"
    assert data["warehouse_id"] == "WH004"
    assert data["model_name"] == "reorder-forecaster"
    assert data["model_stage"] == "Production"
    assert isinstance(data["prediction"], (int, float))
    assert isinstance(data["recommended_quantity"], int)
    assert data["recommended_quantity"] >= 0
    assert 0.0 < data["confidence_score"] <= 1.0
    assert data["status"] in ("NORMAL", "REORDER_NEEDED", "URGENT")
    assert isinstance(data["action_required"], bool)
    assert len(data["recommendation"]) > 15


def test_ml_stockout_simulation_with_overrides():
    """Verifica que los overrides modifiquen la inferencia (simulación de stock crítico)."""
    payload = {
        "product_id": "PRD0000001",
        "warehouse_id": "WH004",
        "current_stock": 0,
        "reorder_level": 1500,
        "daily_demand": 300,
    }
    response = client.post("/api/v1/ml/stockout", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["operational_context"]["current_stock"] == 0
    assert data["operational_context"]["reorder_level"] == 1500
    assert data["operational_context"]["daily_demand"] == 300.0
    assert data["operational_context"]["stock_coverage_days"] == 0.0
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["action_required"] is True


def test_ml_product_not_found():
    """Verifica código 404 al solicitar un producto inexistente."""
    payload = {
        "product_id": "PRD_NO_EXISTE_999",
        "warehouse_id": "WH004",
    }
    response = client.post("/api/v1/ml/stockout", json=payload)
    assert response.status_code == 404
    assert "no existe" in response.json()["detail"].lower()


def test_ml_warehouse_not_found():
    """Verifica código 404 al solicitar un almacén inexistente."""
    payload = {
        "product_id": "PRD0000001",
        "warehouse_id": "WH_NO_EXISTE_999",
    }
    response = client.post("/api/v1/ml/reorder", json=payload)
    assert response.status_code == 404
    assert "no existe" in response.json()["detail"].lower()


def test_ml_invalid_payload():
    """Verifica código 422 ante payload inválido (faltan campos obligatorios)."""
    payload = {
        "warehouse_id": "WH004"
        # falta product_id
    }
    response = client.post("/api/v1/ml/stockout", json=payload)
    assert response.status_code == 422
