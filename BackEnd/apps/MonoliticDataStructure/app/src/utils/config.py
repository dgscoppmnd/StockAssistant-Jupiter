import os

from dotenv import load_dotenv

load_dotenv()


def get_setting(name: str, default=None):
    return os.getenv(name, default)
