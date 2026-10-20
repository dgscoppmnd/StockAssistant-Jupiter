from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# Compatibility import for callers of the historical database module.
from src.api.models import Product


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer)
    name = Column(String)
    country = Column(String)
