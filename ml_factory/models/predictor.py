"""Carga de modelos registrados en MLflow para inferencia."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import mlflow


class Predictor:
    """Predice usando una version del Model Registry de MLflow.

    Args:
        model_name: Nombre registrado en MLflow.
        stage: Stage o alias compatible con la URI de MLflow.
        tracking_uri: Servidor MLflow.
    """

    def __init__(self, model_name: str, stage: str = "Production", tracking_uri: str | None = None) -> None:
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        self.model_uri = f"models:/{model_name}/{stage}"
        self.model = mlflow.pyfunc.load_model(self.model_uri)

    def _prepare_frame(self, input_data: Mapping[str, Any] | pd.DataFrame) -> pd.DataFrame:
        """Alinea las columnas de entrada con el esquema del modelo registrado."""
        frame = input_data.copy() if isinstance(input_data, pd.DataFrame) else pd.DataFrame([dict(input_data)])
        feature_names = self._feature_names()
        if feature_names:
            for feature_name in feature_names:
                if feature_name not in frame.columns:
                    frame[feature_name] = 0.0
            frame = frame.reindex(columns=feature_names, fill_value=0.0)
        return frame

    def predict(self, input_data: Mapping[str, Any] | pd.DataFrame) -> Any:
        """Genera predicciones a partir de un registro o DataFrame."""
        frame = self._prepare_frame(input_data)
        return self.model.predict(frame)

    def predict_proba(self, input_data: Mapping[str, Any] | pd.DataFrame) -> Any:
        """Genera probabilidades de clase si el modelo subyacente lo soporta."""
        frame = self._prepare_frame(input_data)
        implementation = getattr(self.model, "_model_impl", None)
        xgb_model = getattr(implementation, "xgb_model", None)
        if hasattr(xgb_model, "predict_proba"):
            return xgb_model.predict_proba(frame)
        raise NotImplementedError("El modelo registrado no soporta predict_proba")

    def _feature_names(self) -> list[str]:
        """Obtiene el esquema de entrada del booster XGBoost registrado."""
        implementation = getattr(self.model, "_model_impl", None)
        xgb_model = getattr(implementation, "xgb_model", None)
        booster = getattr(xgb_model, "get_booster", lambda: None)()
        return list(getattr(booster, "feature_names", None) or [])
