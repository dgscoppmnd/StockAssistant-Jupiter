from pathlib import Path


def ensure_knowledge_schema(connection):
    schema_path = Path(__file__).resolve().parents[1] / "docker/init-scripts/init.sql"
    # El arranque de la API solo migra RAG; no debe repetir los datos iniciales de init.sql.
    script = schema_path.read_text(encoding="utf-8")
    _, begin, remainder = script.partition("-- BEGIN RAG SCHEMA\n")
    schema, end, _ = remainder.partition("-- END RAG SCHEMA")
    if not begin or not end or not schema.strip():
        raise ValueError("No se encuentra el bloque de esquema RAG en init.sql")
    with connection.cursor() as cursor:
        cursor.execute(schema)
    connection.commit()
