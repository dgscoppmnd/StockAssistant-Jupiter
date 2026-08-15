"""Generador de datos para la tabla supply_chain_metrics"""

import random
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator
from .config import SEED

class MetricsGenerator(BaseGenerator):
    """Genera métricas de cadena de suministro basadas en el dataset Kaggle"""

    def get_dependencies(self) -> List[str]:
        """Depende de productos."""
        return ["products"]
    
    def __init__(self, kaggle_data: List[Dict[str, Any]] = None, seed: Optional[int] = None):
        super().__init__()
        self.kaggle_data = kaggle_data
        self.kaggle_df = pd.DataFrame(kaggle_data) if kaggle_data else None
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        """Genera métricas para cada producto en diferentes fechas"""
        
        products = self._get_dependency_ids("products", "product_id")
        metrics = []
        
        if self.kaggle_df is not None and not self.kaggle_df.empty:
            # Usar datos reales de Kaggle
            for idx, row in self.kaggle_df.iterrows():
                product_id = row.get("Product_ID")
                if not product_id:
                    continue
                
                base_date = pd.to_datetime(row.get("Date", datetime.now()))
                
                # Generar métricas para diferentes fechas (históricas y actuales)
                num_metrics = random.randint(3, 8)
                for i in range(num_metrics):
                    # Fechas distribuidas en el tiempo
                    date_offset = random.randint(-365, 30)
                    metric_date = base_date + timedelta(days=date_offset)
                    
                    # Variar ligeramente las métricas
                    metric = {
                        "product_id": product_id,
                        "date": metric_date.strftime("%Y-%m-%d"),
                        "inventory_optimization_score": self._vary_score(row.get("Inventory_Optimization_Score", random.uniform(0, 100))),
                        "supplier_performance_score": self._vary_score(row.get("Supplier_Performance_Score", random.uniform(0, 100))),
                        "supply_chain_efficiency": self._vary_score(row.get("Supply_Chain_Efficiency", random.uniform(0, 100))),
                        "sustainability_score": self._vary_score(row.get("Sustainability_Score", random.uniform(0, 100))),
                        "operational_risk_score": self._vary_score(row.get("Operational_Risk_Score", random.uniform(0, 100)))
                    }
                    metrics.append(metric)
        else:
            # Generar métricas sintéticas
            for product_id in products[:count]:
                # Generar entre 3 y 8 registros de métricas por producto
                num_metrics = random.randint(3, 8)
                for _ in range(num_metrics):
                    metric_date = self.faker.date_time_between(start_date="-2y", end_date="now")
                    
                    metric = {
                        "product_id": product_id,
                        "date": metric_date.strftime("%Y-%m-%d"),
                        "inventory_optimization_score": round(random.uniform(0, 100), 2),
                        "supplier_performance_score": round(random.uniform(0, 100), 2),
                        "supply_chain_efficiency": round(random.uniform(0, 100), 2),
                        "sustainability_score": round(random.uniform(0, 100), 2),
                        "operational_risk_score": round(random.uniform(0, 100), 2),
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    metrics.append(metric)
        
        self.data = metrics
        return metrics
    
    def _vary_score(self, base_score: float, variation: float = 0.15) -> float:
        """Varía ligeramente un score manteniéndolo en el rango 0-100"""
        if base_score is None or base_score == 0:
            return round(random.uniform(10, 90), 2)
        
        # Variación aleatoria de ±15%
        new_score = base_score * (1 + random.uniform(-variation, variation))
        # Mantener en rango
        new_score = max(0, min(100, new_score))
        return round(new_score, 2)