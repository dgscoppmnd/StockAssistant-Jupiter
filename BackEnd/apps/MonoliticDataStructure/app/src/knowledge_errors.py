"""Errores compartidos por la extracción, vectorización y consulta del RAG."""


class KnowledgeError(Exception):
    """Error de dominio que puede mostrarse al usuario sin exponer detalles internos."""
