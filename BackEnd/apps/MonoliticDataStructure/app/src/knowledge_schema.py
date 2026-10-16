from database_schema import schema_sql


def ensure_knowledge_schema(connection):
    schema = schema_sql('RAG SCHEMA')
    with connection.cursor() as cursor:
        cursor.execute(schema)
    connection.commit()
