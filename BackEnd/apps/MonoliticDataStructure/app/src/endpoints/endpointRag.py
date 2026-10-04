"""Chat documental con recuperación y selección compartida de proveedor."""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_service import AIProviderError
from knowledge_errors import KnowledgeError
from src.vector_store.knowledge_rag import answer_rag

router = APIRouter(prefix="/rag", tags=["RAG"])
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=3, ge=1, le=10)
    target_zone: Literal[
        "auto",
        "general",
        "inventario",
        "ventas",
        "logistica",
        "analiticas",
        "metricas",
        "producto",
        "proveedores",
    ] | None = None


class Citation(BaseModel):
    source: str
    page: int | None = None
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    used_fallback: bool = False
    ingestion_warnings: list[str] = Field(default_factory=list)


@router.post("/ask", response_model=QueryResponse)
def handle_rag_question(request: QueryRequest):
    # FastAPI ejecuta el trabajo de disco, embeddings y LLM en un hilo.
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
    try:
        return answer_rag(request.question.strip(), request.top_k, request.target_zone)
    except AIProviderError as exc:
        logger.warning("event=rag_provider_unavailable provider=%s reason=%s", exc.provider, exc)
        raise HTTPException(
            status_code=503,
            detail="No hay proveedor de IA disponible. Comprueba Ollama o la configuración de OpenAI.",
        ) from exc
    except KnowledgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("event=rag_failed")
        raise HTTPException(
            status_code=503,
            detail="No se pudo consultar la base de conocimiento. Comprueba Qdrant y el índice documental.",
        ) from exc
