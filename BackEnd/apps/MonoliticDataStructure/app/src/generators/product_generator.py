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

    def _build_product_content(
        self,
        product_id: str,
        category: str,
        brand: str,
        sku: str,
        cost: float,
        price: float,
    ) -> Dict[str, str]:
        """Construye contenido comercial variado para los chunks vectoriales."""
        category_data = {
            "Electronics": {
                "products": ["portátil", "monitor", "tablet", "smartphone", "auriculares"],
                "details": [
                    lambda: f"{random.choice([8, 16, 32, 64])} GB de RAM, procesador {random.choice(['i5-1240H', 'i7-12284H', 'Ryzen 5 5600H', 'M2'])} y pantalla de {random.choice([13, 14, 15, 16, 17])} pulgadas",
                    lambda: f"conectividad Bluetooth 5.3, batería de larga duración y almacenamiento SSD de {random.choice([256, 512, 1000, 2000])} GB",
                ],
                "colors": ["gris", "negro", "azul", "blanco"],
            },
            "Fashion": {
                "products": ["chaqueta", "zapatillas", "camiseta", "mochila", "pantalón"],
                "details": [
                    lambda: f"talla {random.choice(['S', 'M', 'L', 'XL'])}, tejido {random.choice(['de algodón', 'técnico transpirable', 'vaquero', 'impermeable'])}",
                    lambda: f"diseño {random.choice(['urbano', 'minimalista', 'deportivo', 'atemporal'])} para uso diario",
                ],
                "colors": ["gris", "negro", "azul marino", "verde", "blanco"],
            },
            "Home": {
                "products": ["lámpara", "silla", "organizador", "alfombra", "estantería"],
                "details": [
                    lambda: f"fabricado en {random.choice(['madera natural', 'metal reforzado', 'bambú', 'polipropileno'])} y pensado para espacios {random.choice(['pequeños', 'modernos', 'multifuncionales'])}",
                    lambda: f"acabado {random.choice(['mate', 'texturizado', 'natural', 'satinado'])} y montaje sencillo",
                ],
                "colors": ["gris", "negro", "blanco", "roble", "verde oliva"],
            },
            "Food": {
                "products": ["café", "té", "snack", "pasta", "aceite de oliva"],
                "details": [
                    lambda: f"elaborado con ingredientes seleccionados y formato de {random.choice([250, 500, 750, 1000])} g",
                    lambda: f"perfil {random.choice(['suave y equilibrado', 'intenso y aromático', 'crujiente y sabroso', 'mediterráneo'])}, ideal para disfrutar a diario",
                ],
                "colors": ["clásico", "natural", "premium", "artesanal"],
            },
            "Beauty": {
                "products": ["crema facial", "champú", "perfume", "serum", "protector solar"],
                "details": [
                    lambda: f"fórmula con {random.choice(['ácido hialurónico', 'aloe vera', 'vitamina C', 'extracto de té verde'])} y textura ligera",
                    lambda: f"envase de {random.choice([50, 100, 150, 250])} ml, pensado para una rutina {random.choice(['hidratante', 'reparadora', 'diaria', 'revitalizante'])}",
                ],
                "colors": ["rosa", "blanco", "dorado", "azul", "transparente"],
            },
            "Health": {
                "products": ["tensiómetro", "termómetro digital", "suplemento", "masajeador", "kit de primeros auxilios"],
                "details": [
                    lambda: f"solución práctica para el cuidado {random.choice(['diario', 'personal', 'en casa', 'deportivo'])}, con diseño fácil de utilizar",
                    lambda: f"fabricado con materiales {random.choice(['resistentes', 'seguros', 'hipoalergénicos', 'de grado sanitario'])} y formato cómodo",
                ],
                "colors": ["blanco", "azul", "verde", "gris", "turquesa"],
            },
            "Sports": {
                "products": ["bicicleta", "mancuernas", "esterilla", "balón", "reloj deportivo"],
                "details": [
                    lambda: f"diseñado para entrenamiento {random.choice(['en casa', 'al aire libre', 'de fuerza', 'de resistencia'])} y uso frecuente",
                    lambda: f"material {random.choice(['antideslizante', 'ligero', 'resistente al agua', 'de alta densidad'])} para mayor comodidad",
                ],
                "colors": ["negro", "rojo", "azul", "verde", "gris"],
            },
            "Toys": {
                "products": ["juego de construcción", "peluche", "puzzle", "coche teledirigido", "juego de mesa"],
                "details": [
                    lambda: f"propuesta para edades de {random.choice([3, 5, 6, 8, 10])} años en adelante, pensada para aprender jugando",
                    lambda: f"incluye {random.choice([24, 48, 100, 250])} piezas y fomenta la creatividad",
                ],
                "colors": ["multicolor", "azul", "rojo", "amarillo", "verde"],
            },
            "Books": {
                "products": ["novela", "guía práctica", "ensayo", "álbum ilustrado", "manual"],
                "details": [
                    lambda: f"edición de {random.choice([180, 240, 320, 480])} páginas sobre {random.choice(['aventuras', 'tecnología', 'bienestar', 'historia', 'creatividad'])}",
                    lambda: f"formato {random.choice(['tapa blanda', 'tapa dura', 'de bolsillo'])}, ideal para lectores curiosos",
                ],
                "colors": ["rojo", "azul", "verde", "negro", "blanco"],
            },
        }

        data = category_data.get(category, {})
        if not data:
            data = {
                "products": ["producto"],
                "details": [lambda: "diseñado para ofrecer un uso práctico y duradero"],
                "colors": ["gris"],
            }
        product = random.choice(data["products"])
        color = random.choice(data["colors"])
        detail = random.choice(data["details"])()
        product_name = f"{product.capitalize()} {brand} {color}"
        description = (
            f"{product_name} de la categoría {category}: {detail}. "
            f"Una opción de calidad para el día a día. SKU {sku}."
        )
        return {"product_name": product_name, "description": description}
    
    def generate(self, count: int) -> List[Dict[str, Any]]:
        """Genera productos basados en los datos de Kaggle"""
        
        products = []
        
        if self.kaggle_data:
            # Usar datos reales de Kaggle como base
            for row in self.kaggle_data:
                # Generar SKU único siempre
                sku = self._generate_unique_sku()
                product_id = row.get("Product_ID", f"PRD{str(len(products)+1).zfill(8)}")
                category = row.get("Product_Category", random.choice(PRODUCT_CATEGORIES))
                brand = row.get("Brand", random.choice(BRANDS))
                cost = float(row.get("Product_Cost_USD", random.uniform(10, 1000)))
                price = float(row.get("Selling_Price_USD", 0))
                
                product = {
                    "product_id": product_id,
                    **self._build_product_content(product_id, category, brand, sku, cost, price),
                    "product_category": category,
                    "brand": brand,
                    "sku": sku,  # SKU generado, no el del CSV
                    "product_cost_usd": cost,
                    "selling_price_usd": price,
                    "created_at": self.faker.date_time_between(start_date="-3y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
                }
                products.append(product)
        
        # Generar productos adicionales si es necesario
        while len(products) < count:
            price = random.uniform(10, 1000)
            product_id = f"PRD{str(len(products)+1).zfill(8)}"
            category = random.choice(PRODUCT_CATEGORIES)
            brand = random.choice(BRANDS)
            sku = self._generate_unique_sku()
            cost = round(price * 0.6, 2)
            product = {
                "product_id": product_id,
                **self._build_product_content(product_id, category, brand, sku, cost, round(price, 2)),
                "product_category": category,
                "brand": brand,
                "sku": sku,
                "product_cost_usd": cost,
                "selling_price_usd": round(price, 2),
                "created_at": self.faker.date_time_between(start_date="-3y", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
            }
            products.append(product)
        
        self.data = products
        return products