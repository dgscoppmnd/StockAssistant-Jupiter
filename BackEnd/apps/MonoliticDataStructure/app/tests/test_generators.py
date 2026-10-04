from src.generators.product_generator import ProductGenerator
from src.generators.supplier_generator import SupplierGenerator


def test_product_generator_returns_records():
    products = ProductGenerator().generate(count=2)

    assert len(products) == 2
    assert "product_id" in products[0]


def test_supplier_generator_returns_records():
    suppliers = SupplierGenerator().generate(count=2)

    assert len(suppliers) == 2
    assert "supplier_id" in suppliers[0]