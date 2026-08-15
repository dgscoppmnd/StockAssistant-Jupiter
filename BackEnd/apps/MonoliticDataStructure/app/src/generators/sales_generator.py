"""Generador de datos para la tabla sales"""

import random
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator

class SalesGenerator(BaseGenerator):
    """Genera datos de ventas basados en el dataset Kaggle"""

    def get_dependencies(self) -> List[str]:
        """Depende de productos."""
        return ["products"]
    
    def __init__(self, kaggle_data: List[Dict[str, Any]] = None, seed: Optional[int] = None):
        super().__init__()
        self.kaggle_data = kaggle_data
        self.kaggle_df = pd.DataFrame(kaggle_data) if kaggle_data else None
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        """Genera registros de ventas para cada producto"""
        
        products = self._get_dependency_ids("products", "product_id")
        sales = []
        
        if self.kaggle_df is not None and not self.kaggle_df.empty:
            # Usar datos reales de Kaggle como base
            for idx, row in self.kaggle_df.iterrows():
                product_id = row.get("Product_ID")
                if not product_id:
                    continue
                    
                # Crear múltiples registros de ventas (variando fechas)
                base_date = pd.to_datetime(row.get("Date", datetime.now()))
                
                # Generar 3-6 registros de ventas por producto en diferentes fechas
                num_records = random.randint(3, 6)
                for i in range(num_records):
                    # Variar la fecha alrededor de la fecha base (± meses)
                    month_offset = random.randint(-6, 6)
                    sale_date = base_date + timedelta(days=month_offset * 30 + random.randint(-15, 15))
                    
                    # Variar cantidades y precios ligeramente
                    units_multiplier = random.uniform(0.7, 1.3)
                    price_multiplier = random.uniform(0.9, 1.1)
                    
                    units_sold = int(row.get("Units_Sold", 1000) * units_multiplier)
                    daily_demand = int(row.get("Daily_Demand", 100) * units_multiplier)
                    monthly_demand = int(row.get("Monthly_Demand", 3000) * units_multiplier)
                    
                    # Calcular revenue y profit basado en precios del producto
                    product_cost = float(row.get("Product_Cost_USD", 100))
                    selling_price = float(row.get("Selling_Price_USD", 200) * price_multiplier)
                    revenue = units_sold * selling_price
                    profit = units_sold * (selling_price - product_cost)
                    
                    sale = {
                        "product_id": product_id,
                        "date": sale_date.strftime("%Y-%m-%d"),
                        "month": sale_date.month,
                        "quarter": (sale_date.month - 1) // 3 + 1,
                        "year": sale_date.year,
                        "units_sold": units_sold,
                        "daily_demand": daily_demand,
                        "monthly_demand": monthly_demand,
                        "seasonal_demand_index": round(random.uniform(20, 90), 2),
                        "revenue_usd": round(revenue, 2),
                        "profit_usd": round(profit, 2),
                        "demand_forecast": int(monthly_demand * random.uniform(0.8, 1.2)),
                        "predicted_reorder_quantity": random.randint(500, 5000),
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    sales.append(sale)
        else:
            # Generar datos sintéticos si no hay Kaggle
            for product_id in products[:count]:
                base_date = self.faker.date_time_between(start_date="-2y", end_date="now")
                
                for _ in range(random.randint(3, 6)):
                    sale_date = base_date + timedelta(days=random.randint(-180, 180))
                    units_sold = random.randint(100, 5000)
                    
                    sale = {
                        "product_id": product_id,
                        "date": sale_date.strftime("%Y-%m-%d"),
                        "month": sale_date.month,
                        "quarter": (sale_date.month - 1) // 3 + 1,
                        "year": sale_date.year,
                        "units_sold": units_sold,
                        "daily_demand": random.randint(50, 500),
                        "monthly_demand": random.randint(1000, 10000),
                        "seasonal_demand_index": round(random.uniform(20, 90), 2),
                        "revenue_usd": round(random.uniform(1000, 100000), 2),
                        "profit_usd": round(random.uniform(100, 50000), 2),
                        "demand_forecast": random.randint(1000, 15000),
                        "predicted_reorder_quantity": random.randint(500, 5000)
                    }
                    sales.append(sale)
        
        # Limitar a count si es necesario
        if len(sales) > count * 5:  # Aprox 5 registros por producto
            sales = random.sample(sales, count * 5)
        
        self.data = sales
        return sales