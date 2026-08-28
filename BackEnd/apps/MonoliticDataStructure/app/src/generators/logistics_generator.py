"""Generador de datos para la tabla logistics"""

import random
import pandas as pd
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator
from .config import TRANSPORTATION_MODES, SEED
from datetime import datetime, timedelta

class LogisticsGenerator(BaseGenerator):
    """Genera datos de logística basados en el dataset Kaggle"""

    def get_dependencies(self) -> List[str]:
        """Depende de productos, proveedores y almacenes."""
        return ["products", "suppliers", "warehouses"]
    
    def __init__(self, kaggle_data: List[Dict[str, Any]] = None, seed: Optional[int] = None):
        super().__init__()
        self.kaggle_data = kaggle_data
        self.kaggle_df = pd.DataFrame(kaggle_data) if kaggle_data else None
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        """Genera registros logísticos para cada producto"""
        
        products = self._get_dependency_ids("products", "product_id")
        suppliers = self._get_dependency_ids("suppliers", "supplier_id")
        warehouses = self._get_dependency_ids("warehouses", "warehouse_id")
        
        logistics = []
        
        if self.kaggle_df is not None and not self.kaggle_df.empty:
            # Usar datos reales de Kaggle
            for idx, row in self.kaggle_df.iterrows():
                product_id = row.get("Product_ID")
                if not product_id:
                    continue
                
                # Obtener supplier_id (puede ser de Kaggle o aleatorio)
                supplier_id = row.get("Supplier_ID")
                if supplier_id not in suppliers and suppliers:
                    supplier_id = random.choice(suppliers)
                
                # Obtener warehouse_id
                warehouse_id = row.get("Warehouse_ID")
                if warehouse_id not in warehouses and warehouses:
                    warehouse_id = random.choice(warehouses)
                
                logistics_record = {
                    "product_id": product_id,
                    "supplier_id": supplier_id,
                    "warehouse_id": warehouse_id,
                    "shipping_cost_usd": float(row.get("Shipping_Cost_USD", random.uniform(10, 500))),
                    "transportation_mode": row.get("Transportation_Mode", random.choice(TRANSPORTATION_MODES)),
                    "delivery_time_days": int(row.get("Delivery_Time_Days", random.randint(1, 30))),
                    "on_time_delivery_rate": float(row.get("On_Time_Delivery_Rate", random.uniform(70, 99))),
                    "supply_disruption_risk": float(row.get("Supply_Disruption_Risk", random.uniform(10, 90))),
                    "supply_chain_efficiency": float(row.get("Supply_Chain_Efficiency", random.uniform(20, 95))),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                logistics.append(logistics_record)
        else:
            # Generar datos sintéticos
            for product_id in products[:count]:
                supplier_id = random.choice(suppliers) if suppliers else f"SUP{random.randint(1, 100):04d}"
                warehouse_id = random.choice(warehouses) if warehouses else f"WH{random.randint(1, 20):03d}"
                
                logistics_record = {
                    "product_id": product_id,
                    "supplier_id": supplier_id,
                    "warehouse_id": warehouse_id,
                    "shipping_cost_usd": round(random.uniform(10, 500), 2),
                    "transportation_mode": random.choice(TRANSPORTATION_MODES),
                    "delivery_time_days": random.randint(1, 30),
                    "on_time_delivery_rate": round(random.uniform(70, 99), 2),
                    "supply_disruption_risk": round(random.uniform(10, 90), 2),
                    "supply_chain_efficiency": round(random.uniform(20, 95), 2)
                }
                logistics.append(logistics_record)
        
        self.data = logistics
        return logistics