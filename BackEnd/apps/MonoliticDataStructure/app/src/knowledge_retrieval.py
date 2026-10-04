"""Evidencia común para el chat RAG y atención al cliente."""
from DataBaseManagement.dbConectionPostgres import db_context
from knowledge_service import KnowledgeService
from vector_store.knowledge_text import infer_zone


def retrieve_current(question, limit=5, source_type=None, zone=None, connection=None):
    if connection is None:
        with db_context() as db:
            return retrieve_current(question, limit, source_type, zone, db)
    service = KnowledgeService(connection)
    status = service.status()
    evidence = service.retrieve(question, limit=40 if source_type or zone else limit)
    results = []
    for item in evidence:
        kind = item["archivo"].rsplit(".", 1)[-1].lower() if item.get("archivo") else "txt"
        if source_type and kind != source_type:
            continue
        if zone and infer_zone(item["content"]) != zone:
            continue
        results.append(
            {
                **item,
                "text": item["content"],
                "source": item["title"],
                "source_type": kind,
                "reference": item["source"],
            }
        )
    warnings = [
        f"{doc['title']}: {doc['index_error'] or 'documento pendiente de procesar'}"
        for doc in status["documents"]
        if doc["index_status"] != "available"
    ]
    return results[:limit], warnings
