"""CLI para ejecutar entrenamientos de la ML Factory."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

try:
    from .pipelines import TrainingPipeline
    from .utils.logger import configure_logging
except ImportError:  # Permite ejecutar tambien `python ml_factory/main.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ml_factory.pipelines import TrainingPipeline
    from ml_factory.utils.logger import configure_logging

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parsea los argumentos de la linea de comandos."""
    parser = argparse.ArgumentParser(description="Entrena modelos de stock con MLflow")
    parser.add_argument("--target", choices=("stockout", "reorder"), default="stockout")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config" / "config.yaml",
    )
    return parser.parse_args()


def main() -> None:
    """Punto de entrada del entrenamiento."""
    configure_logging()
    args = parse_args()
    result = TrainingPipeline(args.config).run(args.target)
    summary = {
        "target": result["target_type"],
        "run_id": result["run_id"],
        "model_uri": result["model_uri"],
        "metrics": result["metrics"],
    }
    LOGGER.info("Entrenamiento completado:\n%s", json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
