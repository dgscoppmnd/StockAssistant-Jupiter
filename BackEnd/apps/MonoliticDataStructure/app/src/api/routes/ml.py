"""Router para endpoints de Machine Learning (ML Factory).

Expone servicios de predicción de riesgo de rotura de stock (stockout),
recomendación de reabastecimiento (reorder) y estado de salud de modelos en MLflow.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ...ml_service import (
    MLInferenceService,
    ProductNotFoundError,
    WarehouseNotFoundError,
    InsufficientDataError,
    MLFlowConnectionError,
    ModelStageError,
)
from ..schemas import (
    StockoutPredictionRequest,
    StockoutPredictionResponse,
    ReorderPredictionRequest,
    ReorderPredictionResponse,
    MLHealthResponse,
)

LOGGER = logging.getLogger("src.api.routes.ml")

router = APIRouter()


def _get_service() -> MLInferenceService:
    """Obtiene la instancia del servicio de inferencia."""
    return MLInferenceService.get_instance()


@router.post(
    "/stockout",
    response_model=StockoutPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predecir riesgo de rotura de stock",
    description="Evalúa el riesgo de stockout para un producto en un almacén específico utilizando el modelo XGBoost registrado en MLflow en stage Production.",
)
async def predict_stockout(request: StockoutPredictionRequest):
    """
    Predice la probabilidad de rotura de stock.

    - **product_id**: Identificador del producto (ej: PRD0000001)
    - **warehouse_id**: Identificador del almacén (ej: WH004)
    - **current_stock**: (Opcional) Stock actual para simulación
    - **reorder_level**: (Opcional) Punto de reorden para simulación
    - **daily_demand**: (Opcional) Demanda diaria estimada
    """
    service = _get_service()
    overrides = {
        "current_stock": request.current_stock,
        "reorder_level": request.reorder_level,
        "safety_stock": request.safety_stock,
        "daily_demand": request.daily_demand,
    }

    try:
        result = service.predict_stockout(
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            overrides=overrides,
        )
        return result
    except (ProductNotFoundError, WarehouseNotFoundError) as exc:
        LOGGER.warning("Recurso no encontrado para stockout: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InsufficientDataError as exc:
        LOGGER.warning("Datos insuficientes para stockout: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (MLFlowConnectionError, ModelStageError) as exc:
        LOGGER.error("Fallo de MLflow en inferencia de stockout: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Error interno no esperado en predicción de stockout")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al ejecutar inferencia de stockout: {str(exc)}",
        ) from exc


@router.post(
    "/reorder",
    response_model=ReorderPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predecir cantidad recomendada de reorden",
    description="Calcula la cantidad recomendada de reposición / compra para un producto en un almacén utilizando el modelo regresor registrado en MLflow en stage Production.",
)
async def predict_reorder(request: ReorderPredictionRequest):
    """
    Predice la cantidad requerida de reposición.

    - **product_id**: Identificador del producto (ej: PRD0000001)
    - **warehouse_id**: Identificador del almacén (ej: WH004)
    - **current_stock**: (Opcional) Stock actual para simulación
    - **reorder_level**: (Opcional) Punto de reorden para simulación
    - **daily_demand**: (Opcional) Demanda diaria estimada
    """
    service = _get_service()
    overrides = {
        "current_stock": request.current_stock,
        "reorder_level": request.reorder_level,
        "safety_stock": request.safety_stock,
        "daily_demand": request.daily_demand,
    }

    try:
        result = service.predict_reorder(
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            overrides=overrides,
        )
        return result
    except (ProductNotFoundError, WarehouseNotFoundError) as exc:
        LOGGER.warning("Recurso no encontrado para reorder: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InsufficientDataError as exc:
        LOGGER.warning("Datos insuficientes para reorder: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (MLFlowConnectionError, ModelStageError) as exc:
        LOGGER.error("Fallo de MLflow en inferencia de reorder: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Error interno no esperado en predicción de reorder")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al ejecutar inferencia de reorder: {str(exc)}",
        ) from exc


@router.get(
    "/health",
    response_model=MLHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check de modelos ML y servidor MLflow",
    description="Comprueba la conectividad con el servidor MLflow y el estado de registro de los modelos stockout-predictor y reorder-forecaster.",
)
async def get_ml_health():
    """Devuelve el estado de disponibilidad del servidor de MLflow y modelos registrados."""
    service = _get_service()
    try:
        health_data = service.check_health()
        return health_data
    except Exception as exc:
        LOGGER.exception("Fallo al verificar salud de MLflow")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servidor MLflow no disponible: {str(exc)}",
        ) from exc
