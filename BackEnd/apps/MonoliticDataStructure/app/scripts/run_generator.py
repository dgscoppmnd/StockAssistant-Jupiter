#!/usr/bin/env python
"""Script para ejecutar la generación de datos"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Configurar variable de entorno
os.environ['PYTHONPATH'] = str(project_root)

from src.generators.main_generator import run

if __name__ == "__main__":
    print(" Iniciando generación de datos para Supply Chain TFM...")
    print(f" Directorio del proyecto: {project_root}")
    run()