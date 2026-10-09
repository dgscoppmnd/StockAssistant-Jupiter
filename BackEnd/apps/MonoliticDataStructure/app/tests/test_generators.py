from src.generators.product_generator import ProductGenerator
from src.generators.supplier_generator import SupplierGenerator


def test_product_generator_returns_dataframe():
    df = ProductGenerator().generate()
    assert not df.empty
    assert "product_id" in df.columns


def test_supplier_generator_returns_dataframe():
    df = SupplierGenerator().generate()
    assert not df.empty
    assert "supplier_id" in df.columns
