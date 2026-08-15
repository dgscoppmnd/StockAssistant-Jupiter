"""Generador de datos para la tabla products"""

import random
from typing import Dict, Any, List, Optional
from .base_generator import BaseGenerator
from .config import PRODUCT_CATEGORIES, BRANDS, SEED

class ProductGenerator(BaseGenerator):
    """Genera datos de productos"""
    
    def __init__(self, kaggle_data: List[Dict[str, Any]] = None, seed: Optional[int] = None):
        # Pasar el seed al constructor de la clase base
        super().__init__(seed=seed if seed is not None else SEED)
        self.kaggle_data = kaggle_data

    def get_dependencies(self) -> list:
        """Productos no depende de ninguna otra tabla"""
        return []
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        """Genera productos basados en los datos de Kaggle"""
        
        products = []
        
        if self.kaggle_data:
            # Usar datos reales de Kaggle como base
            for row in self.kaggle_data:
                # Generar SKU único siempre
                sku = self._generate_unique_sku()
                
                product = {
                    "product_id": row.get("Product_ID", f"PRD{str(len(products)+1).zfill(8)}"),
                    "product_category": row.get("Product_Category", random.choice(PRODUCT_CATEGORIES)),
                    "brand": row.get("Brand", random.choice(BRANDS)),
                    "sku": sku,  # SKU generado, no el del CSV
                    "product_cost_usd": float(row.get("Product_Cost_USD", random.uniform(10, 1000))),
                    "selling_price_usd": float(row.get("Selling_Price_USD", 0)),
                    "created_at": self.faker.date_time_between(start_date="-3y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
                }
                products.append(product)
        
        # Generar productos adicionales si es necesario
        while len(products) < count:
            price = random.uniform(10, 1000)
            product = {
                "product_id": f"PRD{str(len(products)+1).zfill(8)}",
                "product_category": random.choice(PRODUCT_CATEGORIES),
                "brand": random.choice(BRANDS),
                "sku": self._generate_unique_sku(),
                "product_cost_usd": round(price * 0.6, 2),
                "selling_price_usd": round(price, 2),
                "created_at": self.faker.date_time_between(start_date="-3y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
            }
            products.append(product)
        
        self.data = products
        return products