"""Apply the sales-only migration without replaying initial seed data."""
from database_schema import schema_sql


def sales_schema_sql() -> str:
    return schema_sql('SALES MODULE')
