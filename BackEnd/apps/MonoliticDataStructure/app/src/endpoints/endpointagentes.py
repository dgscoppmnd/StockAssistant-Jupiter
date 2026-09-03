import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from DataBaseManagement.dbConectionPostgres import get_db_products
from ai_service import AIProviderError, AIService
from ollama_service import get_system_prompt
from security import require_api_key
from .endpointTools import tool_search_products_db
from .endpointWebs import search_web_duckduckgo

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger("api.endpointAgentes")
ai_service = AIService()


class AgentChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    provider: Literal["openai", "ollama"] = "openai"
    use_web: bool = True
    use_tools: bool = True
    max_web_results: int = Field(default=5, ge=1, le=10)
    max_tool_results: int = Field(default=10, ge=1, le=100)


def _infer_tools_from_prompt(prompt: str) -> dict[str, bool]:
    lowered = prompt.lower()
    return {
        "products": any(token in lowered for token in ["producto", "productos", "electro", "tienda", "market"]),
    }


def _format_web_results(web_results: list[dict[str, Any]]) -> str:
    if not web_results:
        return "Sin resultados web."

    lines: list[str] = []
    for idx, row in enumerate(web_results, start=1):
        lines.append(
            f"[{idx}] {row.get('title', '')}\n"
            f"URL: {row.get('url', '')}\n"
            f"Extracto: {row.get('snippet', '')}"
        )
    return "\n\n".join(lines)


def _format_tool_results(tool_results: dict[str, Any]) -> str:
    if not tool_results:
        return "Sin resultados de tools."
    return json.dumps(tool_results, ensure_ascii=False, indent=2, default=str)


def _safe_provider_response(provider: str, prompt: str, system_prompt: str) -> dict[str, Any] | None:
    try:
        return ai_service.generate_for_provider(provider, prompt, system_prompt)
    except (AIProviderError, ValueError) as exc:
        logger.info("event=agent_provider_skipped provider=%s reason=%s", provider, str(exc))
        return None


def _primary_provider_response(provider: str, prompt: str, system_prompt: str) -> dict[str, Any]:
    try:
        return ai_service.generate_for_provider(provider, prompt, system_prompt)
    except AIProviderError as exc:
        status_code = 503 if exc.retryable else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/stockassistant/chat")
def stockassistant_chat(
    request: AgentChatRequest,
    _api_key: str = Depends(require_api_key),
    db_products=Depends(get_db_products),
):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="El prompt es obligatorio")

    inferred = _infer_tools_from_prompt(prompt)
    web_results: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}

    if request.use_web:
        web_query = prompt
        if inferred["products"] and "electron" not in web_query.lower():
            web_query = f"{prompt} productos electronicos tiendas"

        web_results = search_web_duckduckgo(query=web_query, max_results=request.max_web_results)

    if request.use_tools:
        if inferred["products"]:
            tool_results["products_db"] = tool_search_products_db(
                connection=db_products,
                query=prompt,
                limit=min(request.max_tool_results, 20),
            )

    system_prompt = get_system_prompt() + (
        " Usa SOLO espanol. Explica con lenguaje sencillo y evita jerga innecesaria. "
        "Empieza con un resumen directo de una o dos frases y despues desarrolla la respuesta "
        "en secciones breves o listas cuando mejoren la claridad. No muestres ni menciones "
        "la estructura interna, JSON o nombres de campos de los resultados de tools; interpreta "
        "esos datos para el usuario. Si tienes contexto web, cita las URLs usadas al final. "
        "Si no hay datos suficientes, indicalo de forma explicita."
    )

    context_prompt = (
        "Contexto para responder con precision:\n\n"
        f"[RESULTADOS WEB]\n{_format_web_results(web_results)}\n\n"
        f"[RESULTADOS TOOLS]\n{_format_tool_results(tool_results)}\n\n"
        f"[PREGUNTA USUARIO]\n{prompt}"
    )

    logger.info(
        "event=agent_stockassistant_chat use_web=%s use_tools=%s web_count=%s tool_keys=%s",
        request.use_web,
        request.use_tools,
        len(web_results),
        list(tool_results.keys()),
    )

    model_result = _primary_provider_response(request.provider, context_prompt, system_prompt)
    provider_status = ai_service.status()
    primary_provider = model_result.get("provider") or request.provider
    secondary_provider = "ollama" if primary_provider == "openai" else "openai"
    secondary_result = _safe_provider_response(secondary_provider, context_prompt, system_prompt)

    return {
        "agent": "stockassistant",
        "response": model_result.get("response", ""),
        "provider": model_result.get("provider"),
        "model": model_result.get("model"),
        "used_fallback": model_result.get("used_fallback", False),
        "responses": {
            "primary": model_result,
            "secondary": secondary_result,
        },
        "web_results": web_results,
        "tool_results": tool_results,
        "meta": {
            "used_web": request.use_web,
            "used_tools": request.use_tools,
            "inferred": inferred,
            "selected_provider": request.provider,
            "ai": provider_status,
        },
    }
