"""Configuracion centralizada de logging."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configura logging para ejecuciones CLI y notebooks.

    Args:
        level: Nivel base del logger raiz.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
