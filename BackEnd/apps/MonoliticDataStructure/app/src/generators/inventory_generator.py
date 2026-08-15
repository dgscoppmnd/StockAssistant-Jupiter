"""Generador de datos para la tabla inventory"""

import random
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator
from .config import SEED

class InventoryGenerator(BaseGenerator):
    """Genera datos de inventario"""

    def __init__(self, seed: Optional[int] = None):
        super().__init__(seed=seed if seed is not None else SEED)

    def get_dependencies(self) -> List[str]:
        """Depende de productos y almacenes."""
        return ["products", "warehouses"]
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        products = self._get_dependency_ids("products", "product_id")
        warehouses = self._get_dependency_ids("warehouses", "warehouse_id")
        
        inventory = []
        used_combinations = set()
        
        for product_id in products[:count]:
            num_warehouses = random.randint(1, min(3, len(warehouses)))
            selected_warehouses = random.sample(warehouses, num_warehouses)
            
            for warehouse_id in selected_warehouses:
                combination = (product_id, warehouse_id)
                if combination in used_combinations:
                    continue
                
                stock = random.randint(0, 10000)
                inventory_record = {
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "current_stock": stock,
                    "reorder_level": random.randint(50, 1000),
                    "safety_stock": random.randint(50, 500),
                    "inventory_turnover": round(random.uniform(0.5, 20), 2),
                    "stockout_risk": round(random.uniform(0, 100), 2),
                    "overstock_risk": round(random.uniform(0, 100), 2),
                    "inventory_optimization_score": round(random.uniform(0, 100), 2),
                    "operational_risk_score": round(random.uniform(0, 100), 2),
                    "created_at": self.faker.date_time_between(start_date="-1y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
                }
                inventory.append(inventory_record)
                used_combinations.add(combination)
        
        self.data = inventory
        return inventory