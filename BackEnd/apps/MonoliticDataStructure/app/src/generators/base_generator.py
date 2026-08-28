"""Clase base para generadores de datos"""

import csv
import random
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import pandas as pd
from faker import Faker

from .config import SEED

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseGenerator(ABC):
    """Clase base para todos los generadores"""
    
    def __init__(self, seed: Optional[int] = None):
        # Si no se proporciona seed, usar el de config
        if seed is None:
            seed = SEED
        
        self.faker = Faker()
        
        # Establecer seed si es un entero válido
        if seed is not None and isinstance(seed, int):
            try:
                self.faker.seed_instance(seed)
                random.seed(seed)
                logger.debug(f"Seed establecido: {seed}")
            except Exception as e:
                logger.warning(f"No se pudo establecer seed: {e}. Usando seed aleatorio.")
        
        self.data: List[Dict[str, Any]] = []
        self._ids: Set[str] = set()
        self._skus: Set[str] = set()  # Para SKUs únicos
        
    @abstractmethod
    def generate(self, count: int) -> List[Dict[str, Any]]:
        """Genera datos para la tabla"""
        pass
    
    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """Retorna los IDs de los generadores de los que depende"""
        return []
    
    def set_dependency_data(self, dependency_name: str, data: List[Dict[str, Any]]):
        """Inyecta datos de dependencias"""
        setattr(self, f"_{dependency_name}_data", data)
    
    def _get_dependency_ids(self, dependency_name: str, field: str = "id") -> List[str]:
        """Obtiene IDs de una dependencia"""
        data = getattr(self, f"_{dependency_name}_data", [])
        return [row[field] for row in data if field in row]
    
    def _sample_dependency_id(self, dependency_name: str, field: str = "id") -> Optional[str]:
        """Toma un ID aleatorio de una dependencia"""
        ids = self._get_dependency_ids(dependency_name, field)
        return random.choice(ids) if ids else None
    
    def save_to_csv(self, filepath: Path, mode: str = 'w'):
        """Guarda los datos generados en CSV"""
        if not self.data:
            logger.warning(f"No hay datos para guardar en {filepath}")
            return
        
        df = pd.DataFrame(self.data)
        df.to_csv(filepath, index=False, mode=mode)
        logger.info(f"Guardados {len(self.data)} registros en {filepath}")
    
    def _generate_unique_id(self, prefix: str, existing_ids: Set[str]) -> str:
        """Genera un ID único"""
        import uuid
        while True:
            unique_id = f"{prefix}{str(uuid.uuid4())[:8].upper()}"
            if unique_id not in existing_ids:
                existing_ids.add(unique_id)
                return unique_id
    
    def _generate_unique_sku(self, prefix: str = "SKU") -> str:
        """Genera un SKU único"""
        import uuid
        while True:
            sku = f"{prefix}{str(uuid.uuid4())[:8].upper()}"
            if sku not in self._skus:
                self._skus.add(sku)
                return sku