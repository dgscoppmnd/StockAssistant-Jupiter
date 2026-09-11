"""Orquestacion completa del entrenamiento de la ML Factory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ..data import DataLoader
from ..features import FeatureBuilder
from ..models import ModelTrainer

LOGGER = logging.getLogger(__name__)


class TrainingPipeline:
    """Ejecuta Load -> Features -> Train -> Evaluate -> Register.

    Args:
        config_path: Ruta al YAML de configuracion.
    """

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()
        database = self.config["database"]
        self.loader = DataLoader(database["url"], database.get("tables"))
        self.feature_builder = FeatureBuilder()

    def _load_config(self) -> dict[str, Any]:
        """Lee y valida la configuracion YAML."""
        with self.config_path.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        for required in ("database", "model", "mlflow"):
            if required not in config:
                raise ValueError(f"Falta la seccion de configuracion: {required}")
        return config

    def run(self, target_type: str = "stockout") -> dict[str, Any]:
        """Ejecuta el pipeline para el target solicitado."""
        if target_type not in {"stockout", "reorder"}:
            raise ValueError("target_type debe ser stockout o reorder")
        LOGGER.info("Cargando dataset unido para target=%s", target_type)
        raw = self.loader.get_joined_dataset()
        X, y = self.feature_builder.build_full_dataset(raw, target_type)
        model_config = self.config["model"][target_type]
        global_params = self.config["model"].get("params", {})
        trainer = ModelTrainer(
            model_params=global_params,
            tracking_uri=self.config["mlflow"].get("tracking_uri"),
            experiment_name=self.config["mlflow"].get("experiment_name", "stockassistant-ml-factory"),
            registered_model_name=model_config["name"],
        )
        result = trainer.train(X, y, task_type=model_config["type"])
        result["target_type"] = target_type
        result["feature_names"] = list(X.columns)
        return result
