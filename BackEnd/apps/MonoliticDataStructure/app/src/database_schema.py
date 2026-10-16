"""Read every initialization/migration block from the single canonical SQL file."""
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'docker' / 'init-scripts' / 'init.sql'


def schema_sql(block: str = 'JUPITER SCHEMA') -> str:
    source = SCHEMA_PATH.read_text(encoding='utf-8')
    begin, end = f'-- BEGIN {block}\n', f'-- END {block}'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError(f'Bloque de esquema ausente o duplicado: {block}')
    body = source.split(begin, 1)[1].split(end, 1)[0].strip()
    if not body:
        raise ValueError(f'Bloque de esquema vacío: {block}')
    return body
