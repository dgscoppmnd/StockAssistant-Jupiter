"""Generador de datos para la tabla suppliers"""

import random
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator
from .config import SEED

class SupplierGenerator(BaseGenerator):
    """Genera datos de proveedores"""

    def __init__(self, seed: Optional[int] = None):
        super().__init__(seed=seed if seed is not None else SEED)

    def get_dependencies(self) -> List[str]:
        """No depende de otros generadores."""
        return []
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        suppliers = []
        for i in range(count):
            supplier = {
                "supplier_id": f"SUP{str(i+1).zfill(4)}",
                "supplier_rating": round(random.uniform(1.0, 5.0), 2),
                "lead_time_days": random.randint(5, 60),
                "supplier_performance_score": round(random.uniform(0, 100), 2),
                "sustainability_score": round(random.uniform(0, 100), 2),
                "created_at": self.faker.date_time_between(start_date="-2y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
            }
            suppliers.append(supplier)
        
        self.data = suppliers
        return suppliers