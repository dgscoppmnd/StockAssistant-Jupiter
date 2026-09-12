"""API de preguntas basada en el indice documental de Proyecto Jupiter."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ...ai_service import AIProviderError, generate_ai
from ...rag_prompt import build_rag_prompt
from ...vector_store.knowledge import search_knowledge

router = APIRouter()

SYSTEM_PROMPT = """Responde en espanol solo con la evidencia suministrada.
Si la evidencia no responde la pregunta, di exactamente que no hay informacion suficiente.
No inventes datos operativos, cifras, politicas ni funcionalidades. Cita las fuentes como [Fuente, p. N] cuando haya pagina."""


@router.get("/search")
def retrieve_knowledge(
    q: str = Query(..., min_length=3, description="Pregunta o termino a recuperar"),
    limit: int = Query(5, ge=1, le=10),
    source_type: Literal["pdf", "md", "txt"] | None = None,
):
    """Devuelve los fragmentos y las citas que sustentan una respuesta RAG."""
    evidence = search_knowledge(q, limit=limit, source_type=source_type)
    return {"query": q, "count": len(evidence), "evidence": evidence}


@router.get("/answer")
def answer_from_knowledge(
    q: str = Query(..., min_length=3, description="Pregunta sobre Proyecto Jupiter"),
    limit: int = Query(5, ge=1, le=10),
):
    """Genera una respuesta usando exclusivamente los fragmentos recuperados."""
    evidence = search_knowledge(q, limit=limit)
    if not evidence:
        return {
            "answer": "No hay informacion suficiente en la base documental para responder a esa pregunta.",
            "citations": [],
        }
    try:
        response = generate_ai(build_rag_prompt(q, evidence), system=SYSTEM_PROMPT)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail="No hay proveedor LLM disponible") from exc
    citations = [
        {"source": item["source"], "page": item.get("page"), "score": item["score"]}
        for item in evidence
    ]
    return {"answer": response["response"], "citations": citations, "provider": response["provider"]}
