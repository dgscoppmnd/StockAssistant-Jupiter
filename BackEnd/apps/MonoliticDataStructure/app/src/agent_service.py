from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from ai_service import AIProviderError, generate_ai
from external_connectors import ExternalSourceError, get_connectors


class AgentService:
    def __init__(self, connection: Any):
        self.connection = connection

    def _all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def _one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._all(query, params)
        return rows[0] if rows else None

    def _cache_external(self, *, source: str, operation: str, cache_key: str, payload: dict[str, Any], country: str | None, currency: str | None, reference_url: str | None) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.external_data_cache (source, operation, cache_key, payload, country, currency, reference_url, queried_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '1 hour')
                ON CONFLICT (source, operation, cache_key) DO UPDATE SET payload = EXCLUDED.payload, country = EXCLUDED.country,
                    currency = EXCLUDED.currency, reference_url = EXCLUDED.reference_url, queried_at = CURRENT_TIMESTAMP,
                    expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
            """, (source, operation, cache_key, Json(payload), country, currency, reference_url))
        self.connection.commit()

    def source_statuses(self) -> list[dict[str, Any]]:
        return [connector.status().to_dict() for connector in get_connectors().values()]

    def stock_alerts(self) -> dict[str, Any]:
        alerts = self._all("""
            SELECT s.product_id, TRIM(p.name_product) AS product_name, s.warehouse_id, w.name AS warehouse_name,
                   s.physical_qty, s.reserved_qty, s.physical_qty - s.reserved_qty AS available_qty,
                   c.reorder_point, c.reorder_quantity, u.code AS base_unit_code
            FROM public.inventory_stock_levels s
            JOIN public.productos p ON p.pk_product = s.product_id
            JOIN public.inventory_warehouses w ON w.id = s.warehouse_id
            JOIN public.product_inventory_config c ON c.product_id = s.product_id
            JOIN public.inventory_units u ON u.id = c.base_unit_id
            WHERE (s.physical_qty - s.reserved_qty) <= c.reorder_point
            ORDER BY (s.physical_qty - s.reserved_qty) ASC
        """)
        return {"agent": "stock", "generated_at": datetime.now(timezone.utc).isoformat(), "alerts": alerts, "source": "internal_inventory"}

    def purchase_recommendation(self, product_id: int, country: str = "ES", language: str = "es") -> dict[str, Any]:
        stock = self._one("""
            SELECT s.product_id, TRIM(p.name_product) AS product_name, COALESCE(p.currency, 'EUR') AS currency,
                   SUM(s.physical_qty - s.reserved_qty) AS available_qty, MAX(c.reorder_point) AS reorder_point,
                   MAX(c.reorder_quantity) AS reorder_quantity, u.code AS base_unit_code
            FROM public.inventory_stock_levels s JOIN public.productos p ON p.pk_product = s.product_id
            JOIN public.product_inventory_config c ON c.product_id = s.product_id JOIN public.inventory_units u ON u.id = c.base_unit_id
            WHERE s.product_id = %s GROUP BY s.product_id, p.name_product, p.currency, u.code
        """, (product_id,))
        if not stock:
            raise ValueError("El producto no tiene existencias configuradas para recomendar una compra")
        quantity = Decimal(str(stock["reorder_quantity"])) or max(Decimal("1"), Decimal(str(stock["reorder_point"])) - Decimal(str(stock["available_qty"])))
        evidence: list[dict[str, Any]] = [{"source": "internal_inventory", "available_qty": stock["available_qty"], "reorder_point": stock["reorder_point"]}]
        offers: list[dict[str, Any]] = []
        connector = get_connectors()["serpapi"]
        source_status = connector.status().to_dict()
        if source_status["available"]:
            try:
                raw = connector.shopping(str(stock["product_name"]), country, language)  # type: ignore[attr-defined]
                for item in raw.get("shopping_results", [])[:8]:
                    extracted = item.get("extracted_price")
                    if extracted is None:
                        continue
                    offers.append({"merchant": item.get("source") or item.get("seller"), "price": extracted, "currency": item.get("currency") or stock["currency"], "url": item.get("link"), "country": country.upper(), "queried_at": datetime.now(timezone.utc).isoformat()})
                self._cache_external(source="serpapi", operation="google_shopping", cache_key=f"{product_id}:{country}:{language}", payload=raw, country=country.upper(), currency=str(stock["currency"]), reference_url=raw.get("search_metadata", {}).get("json_endpoint"))
                evidence.append({"source": "serpapi", "offers_found": len(offers), "country": country.upper()})
            except ExternalSourceError as exc:
                source_status["detail"] = str(exc)
        lowest = min((Decimal(str(offer["price"])) for offer in offers), default=None)
        import_factor = Decimal("1") + Decimal(__import__("os").getenv("PURCHASE_IMPORT_COST_RATE", "0"))
        estimated_cost = (lowest * quantity * import_factor) if lowest is not None else None
        result = {"agent": "purchasing", "product_id": product_id, "product_name": stock["product_name"], "recommended_qty": quantity,
                  "base_unit_code": stock["base_unit_code"], "estimated_unit_cost": lowest, "estimated_landed_cost": estimated_cost,
                  "currency": stock["currency"], "offers": offers, "evidence": evidence, "source_status": source_status,
                  "generated_at": datetime.now(timezone.utc).isoformat()}
        try:
            ai = generate_ai(f"Explica brevemente esta recomendacion de compra sin inventar datos: {json.dumps(result, default=str)}", "Eres el agente de compras. Usa solo la evidencia proporcionada.")
            result["explanation"] = ai["response"]
            result["ai"] = {key: ai[key] for key in ("provider", "model", "used_fallback")}
        except AIProviderError:
            result["explanation"] = "Recomendacion calculada con stock y ofertas disponibles; el proveedor de IA no esta disponible."
        return result

    def process_review_batch(self, product_id: int, source: str, reviews: list[dict[str, str]], country: str | None, currency: str | None) -> dict[str, Any]:
        positive = ("bueno", "excelente", "genial", "recomiendo", "perfecto", "great", "good")
        negative = ("malo", "defecto", "roto", "tarde", "poor", "bad", "broken")
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""INSERT INTO public.review_batches (product_id, source, country, currency, status, total_reviews)
                VALUES (%s, %s, %s, %s, 'processing', %s) RETURNING id""", (product_id, source, country, currency, len(reviews)))
            batch_id = cursor.fetchone()["id"]
            positives = negatives = neutral = 0
            for review in reviews:
                text = review["text"].strip()
                lowered = text.lower()
                sentiment = "positive" if any(term in lowered for term in positive) else "negative" if any(term in lowered for term in negative) else "neutral"
                positives += sentiment == "positive"; negatives += sentiment == "negative"; neutral += sentiment == "neutral"
                cursor.execute("""INSERT INTO public.product_reviews (batch_id, source_review_id, rating, review_text, sentiment, reviewed_at)
                    VALUES (%s, %s, %s, %s, %s, %s)""", (batch_id, review.get("external_id"), review.get("rating"), text, sentiment, review.get("reviewed_at") or None))
            summary = {"positive": positives, "negative": negatives, "neutral": neutral, "confidence_score": round((positives + neutral * 0.5) / max(len(reviews), 1), 3)}
            cursor.execute("UPDATE public.review_batches SET status = 'completed', summary = %s, completed_at = CURRENT_TIMESTAMP WHERE id = %s", (Json(summary), batch_id))
        self.connection.commit()
        return {"agent": "reviews", "batch_id": batch_id, "product_id": product_id, "source": source, "processed_reviews": len(reviews), "summary": summary, "generated_at": datetime.now(timezone.utc).isoformat()}
