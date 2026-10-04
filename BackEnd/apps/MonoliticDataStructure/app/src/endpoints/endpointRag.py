# BackEnd/apps/MonoliticDataStructure/app/src/endpoints/endpointRag.py

import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Optional

# Importamos ask_rag e infer_zone desde el módulo de Qdrant
from src.vector_store.knowledge_rag import ask_rag, infer_zone

router = APIRouter(prefix="/rag", tags=["RAG"])

class QueryRequest(BaseModel):
    question: str
    top_k: int = 3
    target_zone: Optional[str] = None  # Opcional: permite al cliente enviar una zona fija si lo requiere
    model_config = ConfigDict(extra="allow") 

class QueryResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=QueryResponse)
async def handle_rag_question(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(
            status_code=400, detail="La pregunta no puede estar vacía."
        )

    try:
        # Si el cliente mandó una zona explícita, la usamos; si no, la inferimos de la pregunta
        target_zone = request.target_zone if request.target_zone else infer_zone(request.question)
        print(f"Zona aplicada para la consulta: '{target_zone}'")

        # Llamamos a ask_rag pasando la zona para que aplique el filtro en Qdrant
        answer = ask_rag(
            query=request.question, 
            top_k=request.top_k, 
            target_zone=target_zone
        )
        
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