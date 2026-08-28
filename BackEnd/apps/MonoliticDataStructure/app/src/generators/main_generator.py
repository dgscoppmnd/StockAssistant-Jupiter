"""Orquestador principal para la generación de datos"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Any, List
from tqdm import tqdm

from .config import KAGGLE_CSV, OUTPUT_FILES, BATCH_SIZE, SEED
from .product_generator import ProductGenerator
from .supplier_generator import SupplierGenerator
from .warehouse_generator import WarehouseGenerator
from .inventory_generator import InventoryGenerator
from .sales_generator import SalesGenerator
from .logistics_generator import LogisticsGenerator
from .metrics_generator import MetricsGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataGeneratorOrchestrator:
    """Orquestador que coordina todos los generadores"""
    
    def __init__(self, seed: int = SEED):
        self.seed = seed
        self.kaggle_data = self._load_kaggle_data()
        self.generators = {}
        self.generated_data = {}
    
    def _load_kaggle_data(self) -> List[Dict[str, Any]]:
        """Carga los datos de Kaggle"""
        if not KAGGLE_CSV.exists():
            logger.warning(f"No se encontró el archivo de Kaggle: {KAGGLE_CSV}")
            return []
        
        try:
            df = pd.read_csv(KAGGLE_CSV)
            logger.info(f"Cargados {len(df)} registros de Kaggle")
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error al cargar Kaggle: {e}")
            return []
    
    def generate_all(self):
        """Genera todos los datos en el orden correcto"""
        
        logger.info("=== INICIANDO GENERACIÓN DE DATOS ===")
        
        # 1. Productos (basado en Kaggle)
        logger.info("Generando productos...")
        product_gen = ProductGenerator(self.kaggle_data, seed=self.seed)
        products = product_gen.generate(len(self.kaggle_data) or 1000)
        product_gen.save_to_csv(OUTPUT_FILES["products"])
        self.generated_data["products"] = products
        self.generators["products"] = product_gen
        
        # 2. Proveedores (basado en Kaggle)
        logger.info("Generando proveedores...")
        supplier_gen = SupplierGenerator(seed=self.seed)
        if self.kaggle_data:
            supplier_ids = list(set([row.get("Supplier_ID") for row in self.kaggle_data if row.get("Supplier_ID")]))
            suppliers = supplier_gen.generate(len(supplier_ids) or 100)
        else:
            suppliers = supplier_gen.generate(100)
        supplier_gen.save_to_csv(OUTPUT_FILES["suppliers"])
        self.generated_data["suppliers"] = suppliers
        self.generators["suppliers"] = supplier_gen
        
        # 3. Almacenes
        logger.info("Generando almacenes...")
        warehouse_gen = WarehouseGenerator(seed=self.seed)
        warehouses = warehouse_gen.generate(20)
        warehouse_gen.save_to_csv(OUTPUT_FILES["warehouses"])
        self.generated_data["warehouses"] = warehouses
        self.generators["warehouses"] = warehouse_gen
        
        # 4. Inventario (depende de productos y warehouses)
        logger.info("Generando inventario...")
        inventory_gen = InventoryGenerator(seed=self.seed)
        inventory_gen.set_dependency_data("products", products)
        inventory_gen.set_dependency_data("warehouses", warehouses)
        inventory_data = inventory_gen.generate(len(products))
        inventory_gen.save_to_csv(OUTPUT_FILES["inventory"])
        self.generated_data["inventory"] = inventory_data
        self.generators["inventory"] = inventory_gen
        
        # 5. Ventas (depende de productos)
        logger.info("Generando ventas...")
        sales_gen = SalesGenerator(self.kaggle_data, seed=self.seed)
        sales_gen.set_dependency_data("products", products)
        sales_data = sales_gen.generate(len(products))
        sales_gen.save_to_csv(OUTPUT_FILES["sales"])
        self.generated_data["sales"] = sales_data
        self.generators["sales"] = sales_gen
        
        # 6. Logística (depende de productos, proveedores, warehouses)
        logger.info("Generando logística...")
        logistics_gen = LogisticsGenerator(self.kaggle_data, seed=self.seed)
        logistics_gen.set_dependency_data("products", products)
        logistics_gen.set_dependency_data("suppliers", suppliers)
        logistics_gen.set_dependency_data("warehouses", warehouses)
        logistics_data = logistics_gen.generate(len(products))
        logistics_gen.save_to_csv(OUTPUT_FILES["logistics"])
        self.generated_data["logistics"] = logistics_data
        self.generators["logistics"] = logistics_gen
        
        # 7. Métricas (depende de productos)
        logger.info("Generando métricas...")
        metrics_gen = MetricsGenerator(self.kaggle_data, seed=self.seed)
        metrics_gen.set_dependency_data("products", products)
        metrics_data = metrics_gen.generate(len(products))
        metrics_gen.save_to_csv(OUTPUT_FILES["metrics"])
        self.generated_data["metrics"] = metrics_data
        self.generators["metrics"] = metrics_gen
        
        logger.info("=== GENERACIÓN DE DATOS COMPLETADA ===")
        logger.info(f"Datos generados en: {OUTPUT_FILES}")
        
        self._print_summary()
        
        return self.generated_data
    
    def _print_summary(self):
        """Imprime un resumen de los datos generados"""
        logger.info("\n=== RESUMEN DE DATOS GENERADOS ===")
        for name, data in self.generated_data.items():
            if data:
                logger.info(f"  {name}: {len(data)} registros")
                if len(data) > 0:
                    sample = data[0]
                    logger.info(f"    Columnas: {list(sample.keys())}")
            else:
                logger.warning(f"  {name}: No se generaron datos")

def run():
    """Función principal para ejecutar desde script"""
    orchestrator = DataGeneratorOrchestrator()
    orchestrator.generate_all()

if __name__ == "__main__":
    run()