"""API de preguntas basada en el indice documental de Proyecto Jupiter."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ai_service import AIProviderError, generate_ai
from ...rag_prompt import NO_INFORMATION_INSTRUCTION, NO_INFORMATION_MESSAGE, build_rag_prompt
from knowledge_retrieval import retrieve_current

router = APIRouter()

SYSTEM_PROMPT = (
    """Responde en espanol solo con la evidencia suministrada.
No inventes datos operativos, cifras, politicas ni funcionalidades. Cita las fuentes como [Fuente, p. N] cuando haya pagina.
"""
    + NO_INFORMATION_INSTRUCTION
)


@router.get("/search")
def retrieve_knowledge(
    q: str = Query(..., min_length=3, description="Pregunta o termino a recuperar"),
    limit: int = Query(5, ge=1, le=10),
    source_type: Literal["pdf", "md", "txt"] | None = None,
):
    evidence, warnings = retrieve_current(q, limit=limit, source_type=source_type)
    return {
        "query": q,
        "count": len(evidence),
        "evidence": evidence,
        "ingestion_warnings": warnings,
    }


@router.get("/answer")
def answer_from_knowledge(
    q: str = Query(..., min_length=3, description="Pregunta sobre Proyecto Jupiter"),
    limit: int = Query(5, ge=1, le=10),
):
    evidence, warnings = retrieve_current(q, limit=limit)
    if not evidence:
        return {
            "answer": NO_INFORMATION_MESSAGE,
            "citations": [],
            "ingestion_warnings": warnings,
        }
    try:
        response = generate_ai(build_rag_prompt(q, evidence), system=SYSTEM_PROMPT)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail="No hay proveedor LLM disponible") from exc
    citations = [
        {"source": item["source"], "page": item.get("page"), "score": item["score"]}
        for item in evidence
    ]
    return {
        "answer": response["response"],
        "citations": citations,
        "provider": response["provider"],
        "ingestion_warnings": warnings,
    }
