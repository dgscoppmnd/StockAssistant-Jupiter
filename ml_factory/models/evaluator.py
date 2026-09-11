"""Metricas y graficos para evaluar modelos de stock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, mean_absolute_error, mean_squared_error


class Evaluator:
    """Calcula metricas comunes y guarda graficos de evaluacion."""

    def calculate_metrics(
        self,
        y_true: pd.Series | np.ndarray,
        y_pred: pd.Series | np.ndarray,
        task_type: str,
    ) -> dict[str, float]:
        """Calcula MAE/RMSE y, en clasificacion, F1/Accuracy."""
        actual = np.asarray(y_true)
        predicted = np.asarray(y_pred)
        metrics = {
            "mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        }
        if task_type == "classification":
            metrics["f1"] = float(f1_score(actual, predicted, zero_division=0))
            metrics["accuracy"] = float(accuracy_score(actual, predicted))
        else:
            metrics["f1"] = 0.0
            metrics["accuracy"] = 0.0
        return metrics

    def plot_confusion_matrix(
        self,
        y_true: pd.Series | np.ndarray,
        y_pred: pd.Series | np.ndarray,
        output_path: str | Path,
    ) -> Path:
        """Genera y guarda una matriz de confusion."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        figure, axis = plt.subplots(figsize=(5, 4))
        sns.heatmap(confusion_matrix(y_true, y_pred), annot=True, fmt="d", cmap="Blues", ax=axis)
        axis.set_xlabel("Prediccion")
        axis.set_ylabel("Real")
        figure.tight_layout()
        figure.savefig(path, dpi=150)
        plt.close(figure)
        return path

    def plot_feature_importance(self, model: Any, feature_names: list[str], output_path: str | Path) -> Path:
        """Genera y guarda las importancias del modelo."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        values = np.asarray(getattr(model, "feature_importances_"))
        importance = pd.Series(values, index=feature_names).sort_values().tail(20)
        figure, axis = plt.subplots(figsize=(8, 6))
        importance.plot.barh(ax=axis, color="#2364aa")
        axis.set_title("Importancia de features")
        figure.tight_layout()
        figure.savefig(path, dpi=150)
        plt.close(figure)
        return path

    def plot_residuals(
        self,
        y_true: pd.Series | np.ndarray,
        y_pred: pd.Series | np.ndarray,
        output_path: str | Path,
    ) -> Path:
        """Genera y guarda el grafico de residuales."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        residuals = np.asarray(y_true) - np.asarray(y_pred)
        figure, axis = plt.subplots(figsize=(7, 4))
        axis.scatter(y_pred, residuals, alpha=0.6)
        axis.axhline(0, color="black", linewidth=1)
        axis.set_xlabel("Prediccion")
        axis.set_ylabel("Residual")
        figure.tight_layout()
        figure.savefig(path, dpi=150)
        plt.close(figure)
        return path
