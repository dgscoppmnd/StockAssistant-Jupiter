"""Entrenamiento XGBoost y registro en MLflow."""

from __future__ import annotations

import logging
from typing import Any

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from .evaluator import Evaluator

LOGGER = logging.getLogger(__name__)


class ModelTrainer:
    """Entrena modelos XGBoost usando una particion temporal.

    Args:
        model_params: Hiperparametros de XGBoost.
        tracking_uri: URI del servidor MLflow.
        experiment_name: Experimento donde se guardan las ejecuciones.
        registered_model_name: Nombre del modelo en el Registry.
    """

    def __init__(
        self,
        model_params: dict[str, Any] | None = None,
        tracking_uri: str | None = None,
        experiment_name: str = "stockassistant-ml-factory",
        registered_model_name: str = "stockout-predictor",
    ) -> None:
        self.model_params = dict(model_params or {})
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        self.registered_model_name = registered_model_name
        self.evaluator = Evaluator()
        self.model: XGBClassifier | XGBRegressor | None = None
        self.feature_names: list[str] = []
        self.run_id: str | None = None

    @staticmethod
    def temporal_split(
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Divide conservando el orden temporal, sin mezclar observaciones."""
        if not 0 < test_size < 1:
            raise ValueError("test_size debe estar entre 0 y 1")
        split_index = max(1, int(len(X) * (1 - test_size)))
        if split_index >= len(X):
            split_index = len(X) - 1
        if split_index < 1:
            raise ValueError("Se necesitan al menos dos observaciones")
        return X.iloc[:split_index], X.iloc[split_index:], y.iloc[:split_index], y.iloc[split_index:]

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        task_type: str = "classification",
        test_size: float = 0.2,
    ) -> dict[str, Any]:
        """Entrena, evalua y registra un modelo.

        Returns:
            Diccionario con modelo, metricas, run_id y URI registrada.
        """
        if task_type not in {"classification", "regression"}:
            raise ValueError("task_type debe ser classification o regression")
        X_train, X_test, y_train, y_test = self.temporal_split(X, y, test_size)
        params = dict(self.model_params)
        params.setdefault("objective", "binary:logistic" if task_type == "classification" else "reg:squarederror")
        params.setdefault("eval_metric", "logloss" if task_type == "classification" else "rmse")
        params.setdefault("random_state", 42)
        model: XGBClassifier | XGBRegressor
        model = XGBClassifier(**params) if task_type == "classification" else XGBRegressor(**params)
        self.feature_names = list(X.columns)

        with mlflow.start_run() as run:
            model.fit(X_train, y_train)
            predictions = model.predict(X_test)
            if task_type == "classification":
                predictions = np.asarray(predictions).astype(int)
            metrics = self.evaluator.calculate_metrics(y_test, predictions, task_type)
            mlflow.log_params({key: value for key, value in params.items() if isinstance(value, (str, int, float, bool))})
            mlflow.log_metrics(metrics)
            mlflow.log_param("task_type", task_type)
            mlflow.log_param("train_rows", len(X_train))
            mlflow.log_param("test_rows", len(X_test))
            model_info = mlflow.xgboost.log_model(
                model,
                artifact_path="model",
                registered_model_name=self.registered_model_name,
            )
            self.run_id = run.info.run_id
            self.model = model
            LOGGER.info("Modelo registrado: %s (%s)", self.registered_model_name, self.run_id)

        return {
            "model": model,
            "metrics": metrics,
            "run_id": self.run_id,
            "model_uri": model_info.model_uri,
            "X_test": X_test,
            "y_test": y_test,
            "predictions": predictions,
        }
