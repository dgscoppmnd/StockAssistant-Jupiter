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

    def predict(self, input_data: Mapping[str, Any] | pd.DataFrame) -> Any:
        """Genera predicciones a partir de un registro o DataFrame."""
        frame = input_data.copy() if isinstance(input_data, pd.DataFrame) else pd.DataFrame([dict(input_data)])
        return self.model.predict(frame)
