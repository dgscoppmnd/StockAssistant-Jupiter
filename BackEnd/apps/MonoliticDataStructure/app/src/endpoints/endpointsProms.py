from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ai_service import get_ai_status
from DataBaseManagement.dbManagementProms import delete_prom_record, insert_prom_record, update_prom_record
from ollama_service import SYSTEM_PROMPT, generate_with_ollama, get_system_prompt
from security import require_api_key


router = APIRouter()

class PromCreateRequest(BaseModel):
    data: dict[str, Any]


class PromUpdateRequest(BaseModel):
    id: Any
    data: dict[str, Any]
    id_column: str = "id_prom"


@router.get("/health")
def health():
    return {"status": "server running"}


@router.get("/systemprompt")
def system_prompt():
    return {"systemPrompt": SYSTEM_PROMPT}


@router.get("/ai/status")
def ai_status(_api_key: str = Depends(require_api_key)):
    return get_ai_status()


@router.post("/analyze")
def analyze(prompt: str, _api_key: str = Depends(require_api_key)):
    return generate_with_ollama(prompt)


@router.post("/analyze-system")
def analyze_system(prompt: str, _api_key: str = Depends(require_api_key)):
    system_prompt = get_system_prompt()
    result = generate_with_ollama(prompt, system=system_prompt)
    return result


@router.post("/proms")
def create_prom(payload: PromCreateRequest):
    try:
        created = insert_prom_record(payload.data)
        return {"status": "created", "record": created}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al crear registro en proms: {exc}") from exc


@router.put("/proms")
def edit_prom(payload: PromUpdateRequest):
    try:
        updated = update_prom_record(payload.id, payload.data, payload.id_column)
        if updated is None:
            raise HTTPException(status_code=404, detail="Registro no encontrado en proms")
        return {"status": "updated", "record": updated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al editar registro en proms: {exc}") from exc

@router.delete("/proms")
def delete_prom(record_id: Any, id_column: str = "id"):
    try:
        deleted = delete_prom_record(record_id, id_column)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Registro no encontrado en proms")
        return {"status": "deleted", "record": deleted}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al eliminar registro en proms: {exc}") from exc
    
