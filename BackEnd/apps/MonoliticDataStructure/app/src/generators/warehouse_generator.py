"""Generador de datos para la tabla warehouses"""

import random
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator
from .config import WAREHOUSE_LOCATIONS, SEED

class WarehouseGenerator(BaseGenerator):
    """Genera datos de almacenes"""

    def __init__(self, seed: Optional[int] = None):
        super().__init__(seed=seed if seed is not None else SEED)

    def get_dependencies(self) -> List[str]:
        """No depende de otros generadores."""
        return []
    
    def generate(self, count: int = 10) -> List[Dict[str, Any]]:
        warehouses = []
        for i in range(count):
            capacity = random.randint(1000, 100000)
            warehouse = {
                "warehouse_id": f"WH{str(i+1).zfill(3)}",
                "warehouse_location": random.choice(WAREHOUSE_LOCATIONS),
                "storage_capacity": capacity,
                "utilization_rate": round(random.uniform(20, 95), 2),
                "created_at": self.faker.date_time_between(start_date="-5y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
            }
            warehouses.append(warehouse)
        
        self.data = warehouses
        return warehouses