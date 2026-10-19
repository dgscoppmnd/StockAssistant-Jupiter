"""Read-only marketing proposals based on confirmed dispatches and search interest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import re
from typing import Any

from ai_service import AIProviderError, generate_ai
from commercial_agent_service import CommercialAgentService
from SystemPrompts.marketing_agent import SYSTEM_PROMPT_MARKETING


CANDIDATE_SQL = """
WITH bounds AS (SELECT %s::timestamptz AS cutoff),
dispatches AS (
    SELECT m.product_id,
           SUM(-m.quantity_signed) FILTER (WHERE m.created_at >= b.cutoff - INTERVAL '30 days') AS recent_qty,
           SUM(-m.quantity_signed) FILTER (WHERE m.created_at < b.cutoff - INTERVAL '30 days') AS previous_qty,
           COUNT(DISTINCT DATE(m.created_at AT TIME ZONE 'UTC'))
               FILTER (WHERE m.created_at >= b.cutoff - INTERVAL '30 days') AS recent_dispatch_days
    FROM public.inventory_movements m CROSS JOIN bounds b
    WHERE m.movement_type = 'dispatch' AND m.quantity_signed < 0
      AND m.created_at >= b.cutoff - INTERVAL '60 days' AND m.created_at < b.cutoff
    GROUP BY m.product_id
), stock AS (
    SELECT product_id, SUM(physical_qty - reserved_qty) AS available_qty
    FROM public.inventory_stock_levels GROUP BY product_id
)
SELECT p.pk_product AS product_id, TRIM(p.name_product) AS product_name,
       COALESCE(d.recent_qty, 0) AS recent_qty, COALESCE(d.previous_qty, 0) AS previous_qty,
       d.recent_dispatch_days, s.available_qty, u.code AS base_unit_code
FROM dispatches d JOIN stock s ON s.product_id = d.product_id
JOIN public.productos p ON p.pk_product = d.product_id
JOIN public.product_inventory_config c ON c.product_id = d.product_id
JOIN public.inventory_units u ON u.id = c.base_unit_id
"""


def select_candidates(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Rank absolute increases, avoiding growth claims from tiny baselines."""
    if not 1 <= limit <= 3:
        raise ValueError("El límite debe estar entre uno y tres")
    eligible = []
    for row in rows:
        recent = Decimal(str(row.get("recent_qty") or 0))
        previous = Decimal(str(row.get("previous_qty") or 0))
        available = Decimal(str(row.get("available_qty") or 0))
        if not all(value.is_finite() for value in (recent, previous, available)):
            continue
        if recent < 10 or previous < 5 or recent <= previous or available <= 0:
            continue
        if int(row.get("recent_dispatch_days") or 0) < 3:
            continue
        name = str(row.get("product_name") or "").strip()
        if not name:
            continue
        eligible.append({
            "product_id": int(row["product_id"]), "product_name": name,
            "recent_qty": recent, "previous_qty": previous,
            "increase_qty": recent - previous,
            "increase_percent": ((recent - previous) / previous * 100).quantize(Decimal("0.01")),
            "recent_dispatch_days": int(row["recent_dispatch_days"]),
            "available_qty": available, "base_unit_code": row["base_unit_code"],
        })
    eligible.sort(key=lambda row: (-row["increase_qty"], -row["increase_percent"], row["product_id"]))
    return eligible[:limit]


def default_campaign(candidate: dict[str, Any]) -> dict[str, str]:
    return {
        "objective": "Comprobar si una campaña de visibilidad puede aprovechar el aumento de despachos.",
        "audience_hypothesis": "Personas interesadas en este tipo de producto; validar el segmento antes de lanzar.",
        "channel": "web",
        "message": f"Descubre {candidate['product_name']}. Consulta sus características y elige según tus necesidades.",
        "reason": "El aumento de despachos justifica estudiar una campaña; no garantiza resultados futuros.",
    }


def parse_campaigns(text: str, ids: set[int]) -> dict[int, dict[str, str]]:
    """Bind each generated draft to a known product; never accept invented IDs."""
    payload = json.loads(text)
    entries = payload.get("campaigns") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or len(entries) != len(ids):
        raise ValueError("Respuesta de Marketing incompleta")
    result = {}
    fields = ("objective", "audience_hypothesis", "channel", "message", "reason")
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Campaña no válida")
        product_id = item.get("product_id")
        if type(product_id) is not int or product_id not in ids or product_id in result:
            raise ValueError("Producto no reconocido en la respuesta")
        if any(not isinstance(item.get(key), str) or not item[key].strip() or len(item[key]) > 1600 for key in fields):
            raise ValueError("Campos de campaña no válidos")
        if item["channel"] not in ("web", "email", "redes_sociales"):
            raise ValueError("Canal no reconocido")
        if re.search(r"[%€$]|\b(?:descuentos?|rebajas?|gratis|ofertas?|garantiz\w*)\b", item["message"], re.IGNORECASE):
            raise ValueError("El mensaje contiene una condición comercial no autorizada")
        if re.search(r"\b(?:mejor(?:es)?|perfect[oa]s?|premium|superior(?:es)?|excelentes?)\b", item["message"], re.IGNORECASE):
            raise ValueError("El mensaje atribuye cualidades no verificadas al producto; usa una invitación neutral")
        result[product_id] = {key: item[key].strip() for key in fields}
    return result


class MarketingService:
    def __init__(self, connection: Any):
        self.commercial = CommercialAgentService(connection)

    def opportunities(self, limit: int = 3, country: str = "ES") -> dict[str, Any]:
        if not 1 <= limit <= 3 or len(country) != 2 or not country.isascii() or not country.isalpha():
            raise ValueError("Indica hasta tres productos y un país de dos letras")
        country = country.upper()
        now = datetime.now(timezone.utc)
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = select_candidates(self.commercial._all(CANDIDATE_SQL, (cutoff,)), limit)
        result: dict[str, Any] = {
            "agent": "marketing", "status": "ok" if candidates else "no_candidates", "country": country,
            "generated_at": now.isoformat(), "ai": None, "ai_attempts": [], "opportunities": [],
            "selection": {
                "recent_start": (cutoff - timedelta(days=30)).date().isoformat(),
                "previous_start": (cutoff - timedelta(days=60)).date().isoformat(),
                "end_exclusive": cutoff.date().isoformat(), "period_days": 30,
                "min_recent_qty": 10, "min_previous_qty": 5, "min_recent_dispatch_days": 3,
                "max_candidates": limit, "ranking": "absolute_increase_then_percent_then_product_id",
            },
            "warnings": [
                "Se comparan unidades despachadas en dos periodos de 30 días completos UTC, no toda la demanda.",
                "El stock disponible es una instantánea; no se reserva para la campaña.",
                "El interés de búsqueda no equivale a ventas ni demuestra estacionalidad.",
                "Validar público, disponibilidad y margen antes de lanzar; no se publican campañas ni se aplican descuentos.",
            ],
            "explanation": "No hay productos que cumplan los mínimos de crecimiento y stock disponible." if not candidates else "",
        }
        for candidate in candidates:
            term = candidate["product_name"]
            # Product names are used verbatim; never invent a more popular category.
            if 2 <= len(term) <= 100:
                external = self.commercial.market_intelligence(term, country, include_ai=False)
                summary = external.get("summary")
                external_evidence = {
                    "term": term, "status": external["status"], "summary": summary,
                    "source": external["source"], "generated_at": external["generated_at"],
                    "related_queries": (external.get("data") or {}).get("related_queries", {}),
                }
            else:
                external_evidence = {"term": term, "status": "invalid_search_term", "summary": None,
                                     "source": {"name": "serpapi", "available": False,
                                                "detail": "El nombre no tiene entre 2 y 100 caracteres; no se consulta."}}
            result["opportunities"].append({
                **candidate, "external": external_evidence, "campaign": default_campaign(candidate),
                "campaign_origin": "template", "state": "draft_requires_review",
            })
        if not candidates:
            return result
        evidence = {"country": country, "generated_at": result["generated_at"],
                    "selection": result["selection"], "warnings": result["warnings"],
                    "candidates": [{key: value for key, value in row.items() if key not in ("campaign", "campaign_origin", "state")}
                                   for row in result["opportunities"]]}
        prompt_evidence = evidence
        for attempt in range(1, 3):
            try:
                ai = generate_ai(json.dumps(prompt_evidence, ensure_ascii=False, default=str), SYSTEM_PROMPT_MARKETING,
                                 timeout_seconds=30 if attempt == 1 else 20, max_output_tokens=1800)
            except AIProviderError as exc:
                result["ai_attempts"].append({"attempt": attempt, "status": "provider_error",
                                              "provider": exc.provider, "retryable": exc.retryable})
                break
            try:
                campaigns = parse_campaigns(ai["response"], {row["product_id"] for row in candidates})
            except (ValueError, KeyError, TypeError) as exc:
                result["ai_attempts"].append({"attempt": attempt, "status": "rejected",
                                              "provider": ai.get("provider"), "model": ai.get("model"),
                                              "reason": str(exc)[:200]})
                prompt_evidence = {**evidence, "retry_instruction": (
                    "La respuesta anterior fue rechazada por el validador: " + str(exc)[:200] +
                    ". Devuelve SOLO el JSON completo para los IDs recibidos. "
                    "Usa mensajes neutrales que inviten a consultar la ficha, sin cualidades, superlativos ni ofertas.")}
                continue
            for row in result["opportunities"]:
                row["campaign"] = campaigns[row["product_id"]]
                row["campaign_origin"] = "ai"
            result["ai"] = {key: ai.get(key) for key in ("provider", "model", "used_fallback")}
            result["ai_attempts"].append({"attempt": attempt, "status": "accepted"})
            break
        if result["ai"] is None:
            result["warnings"].append("No se obtuvo una propuesta de IA válida; se conservan borradores de plantilla y la evidencia.")
        lines = ["Oportunidades de Marketing basadas en despachos confirmados:"]
        for row in result["opportunities"]:
            campaign = row["campaign"]
            external = row["external"]
            summary = external.get("summary") or {}
            external_text = (f"cambio de {summary['change_index_points']} puntos del índice entre bloques completos"
                             if external["status"] == "ok" and summary.get("status") == "descriptive_comparison"
                             else "serie disponible sin comparación suficiente" if external["status"] == "ok"
                             else "sin datos externos suficientes")
            channel = {"web": "web de la tienda", "email": "correo electrónico", "redes_sociales": "redes sociales"}[campaign["channel"]]
            lines.append(f"{row['product_name']}: {row['previous_qty']} → {row['recent_qty']} {row['base_unit_code']} despachadas; "
                         f"disponibles: {row['available_qty']}. Interés externo: {external_text}.\n"
                         f"Propuesta: {campaign['objective']}\nPúblico sugerido: {campaign['audience_hypothesis']}\n"
                         f"Canal: {channel}\nMensaje: {campaign['message']}\nMotivo: {campaign['reason']}")
        lines.append("Borradores para revisión: validar público, stock y margen antes de lanzar. No se ha publicado ninguna campaña.")
        result["explanation"] = "\n\n".join(lines)
        return result
