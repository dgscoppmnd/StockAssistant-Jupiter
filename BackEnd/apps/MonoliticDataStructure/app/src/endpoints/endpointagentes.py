import json
import logging
from copy import copy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from DataBaseManagement.dbConectionPostgres import get_db_products
from ai_service import AIProviderError, AIService
from ollama_service import get_system_prompt
from SystemPrompts.consultation_agent import SYSTEM_PROMPT_CONSULTATION
from SystemPrompts.stockassistant_agent import build_stockassistant_system_prompt
from security import require_api_key
from purchase_plan import normalized, tool_purchase_plan
from .endpointWebs import search_web_duckduckgo

from .endpointTools import (
    tool_get_inventory_risk,
    tool_search_products_db,
    tool_search_products_semantic,
)

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger("api.endpointAgentes")
ai_service = AIService()


class ChatTurn(BaseModel):
    role: Literal['user', 'assistant']
    text: str = Field(max_length=16000)


class AgentChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    provider: Literal["openai", "ollama"] = "openai"
    use_web: bool = True
    use_tools: bool = True
    max_web_results: int = Field(default=5, ge=1, le=10)
    max_tool_results: int = Field(default=10, ge=1, le=100)
    period_days: int = Field(default=30, ge=1, le=365)
    context: Literal['dashboard'] | None = None
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    include_comparison: bool = True


class ConsultationPlan(BaseModel):
    action: Literal['purchases', 'inventory', 'products', 'answer']
    product_query: str = Field(max_length=200)
    warehouse_query: str = Field(max_length=200)
    critical_only: bool
    budget: str | None = Field(pattern=r'^\d{1,12}(\.\d{1,2})?$')
    currency: str | None = Field(pattern=r'^[A-Z]{3}$')

    model_config = {'extra': 'forbid'}


def _plan_consultation(request: AgentChatRequest, inferred: dict[str, bool]):
    """The agent chooses a read-only tool and interprets follow-ups; code validates its arguments."""
    planner = copy(ai_service)  # Never put a request-specific schema on the shared provider.
    planner._ollama_call = planner._call_ollama if getattr(ai_service._ollama_call, '__self__', None) is ai_service else ai_service._ollama_call
    planner._openai_call = planner._call_openai if getattr(ai_service._openai_call, '__self__', None) is ai_service else ai_service._openai_call
    planner.response_schema = ConsultationPlan.model_json_schema()
    planner.max_output_tokens = 700
    history = [turn.model_dump() for turn in request.history]
    try:
        result = planner.generate_for_provider(request.provider, json.dumps({
            'question': request.prompt, 'history': history, 'context': request.context,
        }, ensure_ascii=False),
            SYSTEM_PROMPT_CONSULTATION)
        raw = result.get('response', '').strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        return ConsultationPlan.model_validate_json(raw), None
    except (AIProviderError, ValueError, KeyError, IndexError):
        logger.info('event=agent_consultation_planning_unavailable')
        action = 'purchases' if inferred['purchases'] else 'inventory' if inferred['inventory'] or request.context else 'products' if inferred['products'] else 'answer'
        return ConsultationPlan(action=action, product_query='', warehouse_query='', critical_only=False,
                                budget=None, currency=None), 'No se pudieron interpretar los filtros; se muestra la propuesta general sin ajustes de presupuesto.'


def _infer_tools_from_prompt(prompt: str) -> dict[str, bool]:
    lowered = normalized(prompt)
    return {
        "products": any(
            token in lowered
            for token in [
                "producto",
                "productos",
                "articulo",
                "artículos",
                "auricular",
                "telefono",
                "teléfono",
                "movil",
                "móvil",
                "ordenador",
                "electro",
                "tienda",
                "market",
                "busca",
                "buscar",
                "encuentra",
                "recomienda",
                "similar",
                "catalogo",
            ]
        ),
        "inventory": any(
            token in lowered
            for token in [
                "stock",
                "inventario",
                "existencias",
                "rotura",
                "riesgo",
                "reposición",
                "reposicion",
                "reponer",
                "agotado",
                "agotarse",
                "demanda",
                "disponible",
                "disponibilidad",
                "alerta",
                "critico",
                "agotamiento",
            ]
        ),
        "purchases": any(token in lowered for token in ['compr', 'adquisicion', 'aprovision', 'reabastec', 'repon', 'reposicion', 'presupuesto']),
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


def _semantic_fallback_response(tool_results: dict[str, Any]) -> dict[str, Any] | None:
    """Construye una respuesta útil cuando no hay proveedor LLM disponible."""
    semantic_result = tool_results.get("semantic_products")
    if isinstance(semantic_result, dict):
        products = semantic_result.get("products")
        if semantic_result.get("status") == "empty":
            return {
                "response": semantic_result.get(
                    "message",
                    "No se encontraron productos relacionados en el catálogo.",
                ),
                "provider": "qdrant",
                "model": "semantic-search",
                "used_fallback": True,
            }
    else:
        products = semantic_result

    if not isinstance(products, list) or not products:
        return None

    lines = ["He encontrado estos artículos relacionados en el catálogo:"]
    for index, product in enumerate(products[:10], start=1):
        if not isinstance(product, dict):
            continue
        name = product.get("product_name") or "Artículo sin nombre"
        category = product.get("product_category") or "categoría no disponible"
        brand = product.get("brand") or "marca no disponible"
        score = product.get("score")
        score_text = f" · similitud {float(score):.2f}" if isinstance(score, (int, float)) else ""
        lines.append(f"{index}. {name} · {category} · {brand}{score_text}")

    return {
        "response": "\n".join(lines),
        "provider": "qdrant",
        "model": "semantic-search",
        "used_fallback": True,
    }


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
    consultation = None
    planning_warning = None
    if request.use_tools:
        consultation, planning_warning = _plan_consultation(request, inferred)
        # An explicit purchase request must never be downgraded to a generic answer.
        if inferred['purchases'] and consultation.action == 'answer':
            consultation.action = 'purchases'
    web_results: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}

    if request.use_web:
        web_query = prompt
        if inferred["products"] and "electron" not in web_query.lower():
            web_query = f"{prompt} productos electronicos tiendas"

        web_results = search_web_duckduckgo(query=web_query, max_results=request.max_web_results)

    if request.use_tools:
        if consultation.action in ('inventory', 'purchases') or request.context == 'dashboard':
            tool_results["inventory_risk"] = tool_get_inventory_risk(
                connection=db_products,
                period_days=request.period_days,
            )
        if consultation.action == 'purchases':
            tool_results['purchase_plan'] = tool_purchase_plan(
                connection=db_products, period_days=request.period_days,
                product_query=consultation.product_query, warehouse_query=consultation.warehouse_query,
                critical_only=consultation.critical_only,
                budget=Decimal(consultation.budget) if consultation.budget is not None else None,
                currency=consultation.currency,
                limit=request.max_tool_results,
            )
        if consultation.action == 'products':
            tool_results["products_db"] = tool_search_products_db(
                connection=db_products,
                query=consultation.product_query or prompt,
                limit=min(request.max_tool_results, 20),
            )
            try:
                tool_results["semantic_products"] = tool_search_products_semantic(
                    query=consultation.product_query or prompt,
                    limit=min(request.max_tool_results, 20),
                )
            except Exception as exc:
                logger.exception("event=semantic_product_search_failed")
                tool_results["semantic_products"] = []

    # La primera carga del modelo de embeddings puede fallar durante un reload;
    # reintentar una vez evita que una consulta valida termine en un error del LLM.
    if request.use_tools and consultation.action == 'products' and not tool_results.get("semantic_products"):
        try:
            tool_results["semantic_products"] = tool_search_products_semantic(
                query=consultation.product_query or prompt,
                limit=min(request.max_tool_results, 20),
            )
        except Exception:
            logger.exception("event=semantic_product_search_retry_failed")

    generated_at = datetime.now(timezone.utc).isoformat()
    system_prompt = build_stockassistant_system_prompt(get_system_prompt(), request.context)

    context_prompt = (
        "Contexto para responder con precision:\n\n"
        f"[HISTORIAL CONVERSACIONAL NO VERIFICADO]\n{json.dumps([turn.model_dump() for turn in request.history], ensure_ascii=False)}\n\n"
        f"[CONTEXTO]\nPeríodo de actividad: {request.period_days} días. Pantalla: {request.context}.\n"
        f"Advertencia de interpretación: {planning_warning or 'ninguna'}.\n\n"
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

    if request.provider == "openai" and not ai_service.provider_status("openai")["configured"]:
        model_result = _semantic_fallback_response(tool_results)
        if model_result is None:
            raise HTTPException(status_code=503, detail="OpenAI no está configurado y no hay resultados semánticos")
    else:
        try:
            model_result = _primary_provider_response(request.provider, context_prompt, system_prompt)
        except HTTPException:
            model_result = _semantic_fallback_response(tool_results)
            if model_result is None:
                raise
    provider_status = ai_service.status()
    primary_provider = model_result.get("provider") or request.provider
    secondary_provider = "ollama" if primary_provider == "openai" else "openai"
    secondary_result = _safe_provider_response(secondary_provider, context_prompt, system_prompt) if request.include_comparison else None

    sources = [{'name': 'Inventario, configuración, pedidos de venta y movimientos', 'tool': key}
               if key == 'inventory_risk' else
               {'name': 'Inventario, demanda pendiente, pedidos de compra y recepciones confirmadas', 'tool': key}
               if key == 'purchase_plan' else {'name': 'Catálogo de productos', 'tool': key}
               for key in tool_results]

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
        "purchase_plan": tool_results.get('purchase_plan'),
        "evidence": {'sources': sources, 'generated_at': generated_at,
                     'period_days': request.period_days if 'inventory_risk' in tool_results else None,
                     'warnings': [planning_warning] if planning_warning else []},
        "meta": {
            "used_web": request.use_web,
            "used_tools": bool(tool_results),
            "consultation": consultation.model_dump() if consultation else None,
            "inferred": inferred,
            "selected_provider": request.provider,
            "ai": provider_status,
        },
    }
