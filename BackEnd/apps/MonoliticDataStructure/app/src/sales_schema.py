"""Apply the sales-only migration without replaying initial seed data."""
from pathlib import Path


def sales_schema_sql() -> str:
    source = (Path(__file__).resolve().parents[1] / "docker/init-scripts/init.sql").read_text(
        encoding="utf-8"
    )
    return source.split("-- BEGIN SALES MODULE", 1)[1].split("-- END SALES MODULE", 1)[0]
