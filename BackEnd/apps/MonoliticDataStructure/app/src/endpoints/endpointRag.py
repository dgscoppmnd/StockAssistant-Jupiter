# BackEnd/apps/MonoliticDataStructure/app/src/endpoints/endpointRag.py

import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Importación relativa/absoluta según la ubicación del script
from src.vector_store.knowledge_rag import ask_rag

router = APIRouter(prefix="/rag", tags=["RAG"])

class QueryRequest(BaseModel):
    question: str
    top_k: int = 3

class QueryResponse(BaseModel):
    answer: str

@router.post("/ask", response_model=QueryResponse)
async def handle_rag_question(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(
            status_code=400, detail="La pregunta no puede estar vacía."
        )

    try:
        answer = ask_rag(query=request.question, top_k=request.top_k)
        return QueryResponse(answer=answer)

    except HTTPException:
        raise
    except Exception as e:
        print("--- ERROR EN PIPELINE RAG ---")
        traceback.print_exc()
        print("----------------------------")
        raise HTTPException(
            status_code=500, detail=f"Error en el servidor RAG: {str(e)}"
        )