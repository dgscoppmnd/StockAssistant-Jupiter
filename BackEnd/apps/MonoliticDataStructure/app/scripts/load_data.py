#!/usr/bin/env python
"""Script para ejecutar la carga de datos"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.database.loader import run

if __name__ == "__main__":
    run()