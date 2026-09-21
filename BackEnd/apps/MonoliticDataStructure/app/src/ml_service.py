"""Servicio interno de inferencia de Machine Learning para Proyecto Jupiter.

Orquesta la conexión con MLflow Model Registry, la extracción de contexto
operativo de PostgreSQL y la construcción rigurosa de features mediante
FeatureBuilder para garantizar 100% de paridad con el entrenamiento.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

# Asegurar importación de ml_factory desde la raíz del repositorio
_current_file = Path(__file__).resolve()
# Buscar la raíz del repositorio buscando la carpeta 'ml_factory'
_repo_root = _current_file.parents[4]
if not (_repo_root / "ml_factory").exists():
    for parent in _current_file.parents:
        if (parent / "ml_factory").exists():
            _repo_root = parent
            break

if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from ml_factory.features.feature_builder import FeatureBuilder
from ml_factory.models.predictor import Predictor

from src.api.config import settings
from src.api.database import engine

LOGGER = logging.getLogger("src.ml_service")


# ==============================================================================
# EXCEPCIONES DE DOMINIO ML
# ==============================================================================

class MLError(Exception):
    """Excepción base para errores de inferencia ML."""
    pass


class ProductNotFoundError(MLError):
    """El producto solicitado no existe en la base de datos."""
    pass


class WarehouseNotFoundError(MLError):
    """El almacén solicitado no existe en la base de datos."""
    pass


class InsufficientDataError(MLError):
    """No hay suficientes registros históricos para calcular variables temporales."""
    pass


class MLFlowConnectionError(MLError):
    """No se puede conectar con el servidor MLflow o cargar el modelo."""
    pass


class ModelStageError(MLError):
    """El modelo solicitado no está en el stage requerido."""
    pass


# ==============================================================================
# SERVICIO DE INFERENCIA ML
# ==============================================================================

class MLInferenceService:
    """Servicio singleton para inferencia de modelos de inventario."""

    _instance: Optional[MLInferenceService] = None

    def __init__(self) -> None:
        self.tracking_uri = settings.MLFLOW_TRACKING_URI
        self.stockout_model_name = settings.ML_STOCKOUT_MODEL_NAME
        self.reorder_model_name = settings.ML_REORDER_MODEL_NAME
        self.model_stage = settings.ML_MODEL_STAGE
        self.feature_builder = FeatureBuilder()
        self._predictors: dict[str, Predictor] = {}
        LOGGER.info(
            "MLInferenceService inicializado con MLFLOW_TRACKING_URI=%s, STAGE=%s",
            self.tracking_uri,
            self.model_stage,
        )

    @classmethod
    def get_instance(cls) -> MLInferenceService:
        """Obtiene la instancia única del servicio."""
        if cls._instance is None:
            cls._instance = MLInferenceService()
        return cls._instance

    def get_predictor(self, model_name: str) -> Predictor:
        """Carga y cachea la instancia de Predictor para un modelo de MLflow."""
        cache_key = f"{model_name}:{self.model_stage}"
        if cache_key not in self._predictors:
            try:
                LOGGER.info("Cargando modelo '%s' (stage: %s) desde MLflow...", model_name, self.model_stage)
                predictor = Predictor(
                    model_name=model_name,
                    stage=self.model_stage,
                    tracking_uri=self.tracking_uri,
                )
                self._predictors[cache_key] = predictor
                LOGGER.info("Modelo '%s' cargado exitosamente.", model_name)
            except Exception as exc:
                LOGGER.exception("Error al conectar o cargar el modelo '%s' desde MLflow", model_name)
                raise MLFlowConnectionError(
                    f"No se pudo cargar el modelo '{model_name}' en stage '{self.model_stage}' "
                    f"desde MLflow ({self.tracking_uri}): {str(exc)}"
                ) from exc
        return self._predictors[cache_key]

    def _query_product_and_warehouse(self, product_id: str, warehouse_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Verifica que el producto y almacén existan en PostgreSQL."""
        with engine.connect() as conn:
            # Validar producto
            prod_row = conn.execute(
                text("SELECT product_id, product_name, product_category, brand, product_cost_usd, selling_price_usd "
                     "FROM products WHERE product_id = :product_id"),
                {"product_id": product_id},
            ).mappings().first()
            if not prod_row:
                raise ProductNotFoundError(f"El producto con ID '{product_id}' no existe en la base de datos.")

            # Validar almacén
            wh_row = conn.execute(
                text("SELECT warehouse_id, warehouse_location, storage_capacity, utilization_rate "
                     "FROM warehouses WHERE warehouse_id = :warehouse_id"),
                {"warehouse_id": warehouse_id},
            ).mappings().first()
            if not wh_row:
                raise WarehouseNotFoundError(f"El almacén con ID '{warehouse_id}' no existe en la base de datos.")

            return dict(prod_row), dict(wh_row)

    def _load_historical_context(
        self,
        product_id: str,
        warehouse_id: str,
        overrides: Mapping[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Carga el dataset operativo unido desde PostgreSQL aplicando overrides opcionales."""
        query = text("""
            SELECT
                s.product_id, s.date, s.month, s.quarter, s.year,
                s.units_sold, s.daily_demand, s.monthly_demand,
                s.seasonal_demand_index, s.revenue_usd, s.profit_usd,
                s.demand_forecast, s.predicted_reorder_quantity,
                i.warehouse_id, i.current_stock, i.reorder_level,
                i.safety_stock, i.inventory_turnover, i.stockout_risk,
                i.overstock_risk,
                p.product_name, p.product_category, p.brand,
                p.product_cost_usd, p.selling_price_usd,
                l.supplier_id, l.shipping_cost_usd,
                l.transportation_mode, l.delivery_time_days,
                l.on_time_delivery_rate, l.supply_disruption_risk,
                sup.supplier_rating, sup.lead_time_days,
                sup.supplier_performance_score, sup.sustainability_score,
                w.warehouse_location, w.storage_capacity, w.utilization_rate
            FROM sales AS s
            INNER JOIN products AS p ON p.product_id = s.product_id
            LEFT JOIN inventory AS i ON i.product_id = s.product_id AND i.warehouse_id = :warehouse_id
            LEFT JOIN logistics AS l ON l.product_id = s.product_id AND l.warehouse_id = i.warehouse_id
            LEFT JOIN suppliers AS sup ON sup.supplier_id = l.supplier_id
            LEFT JOIN warehouses AS w ON w.warehouse_id = :warehouse_id
            WHERE s.product_id = :product_id
            ORDER BY s.date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"product_id": product_id, "warehouse_id": warehouse_id})

        if df.empty:
            raise InsufficientDataError(
                f"No hay suficientes registros históricos de ventas para el producto '{product_id}' "
                f"en el almacén '{warehouse_id}' para construir las variables temporales."
            )

        # Si el inventario no estaba enlazado directamente a la venta, rellenar con el inventario actual
        if df["warehouse_id"].isna().all():
            df["warehouse_id"] = warehouse_id

        # Aplicar overrides si fueron provistos en la petición
        if overrides:
            for field, val in overrides.items():
                if val is not None and field in df.columns:
                    # Aplicar override a la última fila (o a toda la serie si es inventario)
                    if field in ("current_stock", "reorder_level", "safety_stock"):
                        df[field] = val
                    elif field == "daily_demand":
                        df.loc[df.index[-1], field] = val

        return df

    def _extract_operational_context(self, df: pd.DataFrame) -> dict[str, Any]:
        """Extrae el estado operativo más reciente para el contexto de respuesta."""
        latest = df.iloc[-1]
        current_stock = int(latest.get("current_stock", 0) or 0)
        reorder_level = int(latest.get("reorder_level", 0) or 0)
        safety_stock = int(latest.get("safety_stock", 0) or 0)
        daily_demand = float(latest.get("daily_demand", 0) or 0.0)

        stock_coverage_days = (
            round(current_stock / daily_demand, 2)
            if daily_demand > 0
            else 999.0
        )

        return {
            "product_name": str(latest.get("product_name", "")),
            "product_category": str(latest.get("product_category", "")),
            "brand": str(latest.get("brand", "")),
            "warehouse_location": str(latest.get("warehouse_location", "")),
            "current_stock": current_stock,
            "reorder_level": reorder_level,
            "safety_stock": safety_stock,
            "daily_demand": daily_demand,
            "stock_coverage_days": stock_coverage_days,
            "lead_time_days": int(latest.get("lead_time_days", 0) or 0),
            "delivery_time_days": int(latest.get("delivery_time_days", 0) or 0),
            "on_time_delivery_rate": float(latest.get("on_time_delivery_rate", 0) or 0.0),
            "inventory_turnover": float(latest.get("inventory_turnover", 0) or 0.0),
            "last_recorded_date": str(latest.get("date", "")),
        }

    def predict_stockout(
        self,
        product_id: str,
        warehouse_id: str,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Calcula la probabilidad y riesgo de rotura de stock."""
        # 1. Validar existencia
        prod_meta, wh_meta = self._query_product_and_warehouse(product_id, warehouse_id)

        # 2. Cargar contexto histórico unido
        df = self._load_historical_context(product_id, warehouse_id, overrides)

        # 3. Construir variables con FeatureBuilder
        X, _ = self.feature_builder.build_full_dataset(df, target_type="stockout")
        features_row = X.iloc[[-1]]

        # 4. Obtener modelo de MLflow y predecir
        predictor = self.get_predictor(self.stockout_model_name)
        prediction_raw = predictor.predict(features_row)
        prediction_val = int(prediction_raw[0])

        try:
            proba_arr = predictor.predict_proba(features_row)
            probability = float(proba_arr[0][1])
        except Exception:
            probability = float(prediction_val)

        # 5. Determinar nivel de riesgo y acción requerida
        if probability >= 0.75:
            risk_level = "CRITICAL"
            action_required = True
        elif probability >= 0.50:
            risk_level = "HIGH"
            action_required = True
        elif probability >= 0.25:
            risk_level = "MEDIUM"
            action_required = False
        else:
            risk_level = "LOW"
            action_required = False

        # 6. Contexto operativo y features clave
        op_context = self._extract_operational_context(df)
        features_used = {
            col: float(features_row[col].iloc[0])
            for col in [
                "daily_demand_lag_7",
                "daily_demand_lag_14",
                "daily_demand_rolling_mean_7",
                "daily_demand_rolling_mean_30",
                "stock_coverage_days",
                "remaining_inventory_days",
                "inventory_turnover_ratio",
                "month_feature",
                "day_of_week",
            ]
            if col in features_row.columns
        }

        # 7. Generar recomendación legible para chat / LLM
        prob_pct = probability * 100
        coverage = op_context["stock_coverage_days"]
        prod_name = op_context["product_name"] or product_id
        wh_loc = op_context["warehouse_location"] or warehouse_id
        lead_time = op_context["lead_time_days"]

        if risk_level == "CRITICAL":
            recommendation = (
                f" ALERTA CRÍTICA: Alto riesgo de rotura de stock ({prob_pct:.1f}%) para '{prod_name}' "
                f"en el almacén {warehouse_id} ({wh_loc}). Con el stock actual de {op_context['current_stock']} unidades "
                f"y demanda diaria de {op_context['daily_demand']:.0f} uds, la cobertura es de solo {coverage:.1f} días, "
                f"inferior al plazo de entrega del proveedor ({lead_time} días). Se requiere emitir orden de compra inmediata."
            )
        elif risk_level == "HIGH":
            recommendation = (
                f" ATENCIÓN: Riesgo elevado de rotura ({prob_pct:.1f}%) para '{prod_name}' en {warehouse_id}. "
                f"El stock actual ({op_context['current_stock']} uds) está próximo al punto de reorden ({op_context['reorder_level']} uds). "
                f"Cobertura estimada: {coverage:.1f} días. Se aconseja iniciar gestión de reposición."
            )
        elif risk_level == "MEDIUM":
            recommendation = (
                f" RIESGO MODERADO: Probabilidad de rotura del {prob_pct:.1f}% para '{prod_name}' en {warehouse_id}. "
                f"El inventario se encuentra en límites aceptables (cobertura: {coverage:.1f} días). Monitorear evolución de demanda."
            )
        else:
            recommendation = (
                f" ESTADO SALUDABLE: Riesgo bajo de rotura ({prob_pct:.1f}%) para '{prod_name}' en {warehouse_id} ({wh_loc}). "
                f"El inventario actual ({op_context['current_stock']} uds) garantiza {coverage:.1f} días de cobertura. No se requieren acciones."
            )

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "model_name": self.stockout_model_name,
            "model_stage": self.model_stage,
            "prediction": prediction_val,
            "probability": round(probability, 4),
            "risk_level": risk_level,
            "action_required": action_required,
            "recommendation": recommendation,
            "operational_context": op_context,
            "features_used": features_used,
            "timestamp": datetime.now(),
        }

    def predict_reorder(
        self,
        product_id: str,
        warehouse_id: str,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Calcula la cantidad recomendada de reposición / reorden."""
        # 1. Validar existencia
        prod_meta, wh_meta = self._query_product_and_warehouse(product_id, warehouse_id)

        # 2. Cargar contexto histórico unido
        df = self._load_historical_context(product_id, warehouse_id, overrides)

        # 3. Construir variables con FeatureBuilder
        X, _ = self.feature_builder.build_full_dataset(df, target_type="reorder")
        features_row = X.iloc[[-1]]

        # 4. Obtener modelo de MLflow y predecir
        predictor = self.get_predictor(self.reorder_model_name)
        prediction_raw = predictor.predict(features_row)
        pred_qty = float(prediction_raw[0])
        recommended_qty = max(0, int(round(pred_qty)))

        # 5. Contexto operativo y features clave
        op_context = self._extract_operational_context(df)
        features_used = {
            col: float(features_row[col].iloc[0])
            for col in [
                "daily_demand_lag_7",
                "daily_demand_lag_14",
                "daily_demand_rolling_mean_7",
                "daily_demand_rolling_mean_30",
                "stock_coverage_days",
                "remaining_inventory_days",
                "inventory_turnover_ratio",
                "month_feature",
                "day_of_week",
            ]
            if col in features_row.columns
        }

        # 6. Estado y confianza
        current_stock = op_context["current_stock"]
        reorder_level = op_context["reorder_level"]

        if recommended_qty > 0 and current_stock <= (reorder_level * 0.5):
            status = "URGENT"
            action_required = True
        elif recommended_qty > 0:
            status = "REORDER_NEEDED"
            action_required = True
        else:
            status = "NORMAL"
            action_required = False

        confidence_score = 0.90 if recommended_qty > 0 else 0.95
        prod_name = op_context["product_name"] or product_id
        wh_loc = op_context["warehouse_location"] or warehouse_id
        lead_time = op_context["lead_time_days"]
        on_time = op_context["on_time_delivery_rate"]

        if status == "URGENT":
            recommendation = (
                f" REORDEN URGENTE: Se aconseja tramitar pedido de compra por {recommended_qty} unidades de '{prod_name}' "
                f"para el almacén {warehouse_id} ({wh_loc}). El stock actual ({current_stock} uds) es crítico frente al punto de reorden ({reorder_level} uds). "
                f"Plazo proveedor: {lead_time} días."
            )
        elif status == "REORDER_NEEDED":
            recommendation = (
                f" RECOMENDACIÓN DE COMPRA: Se sugiere aprovisionar {recommended_qty} unidades de '{prod_name}' "
                f"en {warehouse_id} ({wh_loc}) para cubrir el ciclo de reabastecimiento (lead time de {lead_time} días, "
                f"tasa de cumplimiento proveedor {on_time:.1f}%)."
            )
        else:
            recommendation = (
                f" INVENTARIO ÓPTIMO: No se requiere pedido adicional para '{prod_name}' en {warehouse_id}. "
                f"El stock actual de {current_stock} unidades supera el nivel mínimo de seguridad."
            )

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "model_name": self.reorder_model_name,
            "model_stage": self.model_stage,
            "prediction": round(pred_qty, 2),
            "recommended_quantity": recommended_qty,
            "confidence_score": confidence_score,
            "status": status,
            "action_required": action_required,
            "recommendation": recommendation,
            "operational_context": op_context,
            "features_used": features_used,
            "timestamp": datetime.now(),
        }

    def check_health(self) -> dict[str, Any]:
        """Comprueba la disponibilidad del servidor MLflow y los modelos en producción."""
        import mlflow

        models_status = {}
        all_ok = True

        try:
            client = mlflow.MlflowClient(tracking_uri=self.tracking_uri)
            for model_name in (self.stockout_model_name, self.reorder_model_name):
                try:
                    registered_model = client.get_registered_model(model_name)
                    prod_versions = [
                        v.version for v in registered_model.latest_versions
                        if v.current_stage.lower() == self.model_stage.lower()
                    ]
                    loaded = f"{model_name}:{self.model_stage}" in self._predictors
                    models_status[model_name] = {
                        "registered": True,
                        "stage": self.model_stage,
                        "production_versions": prod_versions,
                        "loaded_in_cache": loaded,
                    }
                    if not prod_versions:
                        all_ok = False
                except Exception as m_exc:
                    models_status[model_name] = {
                        "registered": False,
                        "error": str(m_exc),
                    }
                    all_ok = False
            mlflow_connected = True
        except Exception as exc:
            mlflow_connected = False
            all_ok = False
            LOGGER.exception("Fallo al contactar con MLflow tracking server")

        return {
            "status": "healthy" if all_ok and mlflow_connected else "degraded",
            "mlflow_connected": mlflow_connected,
            "tracking_uri": self.tracking_uri,
            "models": models_status,
            "timestamp": datetime.now(),
        }
