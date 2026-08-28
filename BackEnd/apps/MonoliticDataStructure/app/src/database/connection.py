import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


def get_engine():
    database_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'stockassistant')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'stockassistant')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'stockassistant')}"
    )
    return create_engine(database_url)
