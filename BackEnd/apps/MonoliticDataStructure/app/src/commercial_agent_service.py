from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from ai_service import AIProviderError, generate_ai
from external_connectors import ExternalSourceError, get_connectors


class CommercialAgentError(Exception):
    pass


class CommercialAgentService:
    def __init__(self, connection: Any):
        self.connection = connection

    def _all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def _one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._all(query, params)
        return rows[0] if rows else None

    def _product(self, product_id: int) -> dict[str, Any]:
        product = self._one("SELECT pk_product, TRIM(name_product) AS name_product, description_product, currency, supplier FROM public.productos WHERE pk_product = %s", (product_id,))
        if not product:
            raise CommercialAgentError("Producto no encontrado")
        return product

    def _cache(self, operation: str, cache_key: str, payload: dict[str, Any], country: str, reference_url: str | None) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.external_data_cache (source, operation, cache_key, payload, country, reference_url, queried_at, expires_at)
                VALUES ('serpapi', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '1 hour')
                ON CONFLICT (source, operation, cache_key) DO UPDATE SET payload = EXCLUDED.payload, country = EXCLUDED.country,
                    reference_url = EXCLUDED.reference_url, queried_at = CURRENT_TIMESTAMP, expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
            """, (operation, cache_key, Json(payload), country, reference_url))
        self.connection.commit()

    def sales_forecast(self, product_id: int, horizon_days: int = 30) -> dict[str, Any]:
        product = self._product(product_id)
        rows = self._all("""
            SELECT DATE(created_at) AS day, COALESCE(SUM(-quantity_signed), 0) AS sold_qty
            FROM public.inventory_movements
            WHERE product_id = %s AND movement_type = 'dispatch' AND created_at >= CURRENT_TIMESTAMP - INTERVAL '90 days'
            GROUP BY DATE(created_at) ORDER BY day
        """, (product_id,))
        sold = sum((Decimal(str(row["sold_qty"])) for row in rows), Decimal("0"))
        observed_days = max(len(rows), 1)
        daily_average = sold / Decimal("90")
        recent = sum((Decimal(str(row["sold_qty"])) for row in rows[-30:]), Decimal("0"))
        prior = sum((Decimal(str(row["sold_qty"])) for row in rows[-60:-30]), Decimal("0"))
        trend = "stable" if recent == prior else ("up" if recent > prior else "down")
        return {"agent": "sales_forecast", "product_id": product_id, "product_name": product["name_product"], "horizon_days": horizon_days,
                "forecast_qty": daily_average * Decimal(str(horizon_days)), "daily_average": daily_average, "observed_sales_days": observed_days,
                "trend": trend, "evidence": {"source": "inventory_movements", "period_days": 90, "confirmed_dispatch_qty": sold},
                "generated_at": datetime.now(timezone.utc).isoformat()}

    def financial_summary(self, product_id: int | None = None) -> dict[str, Any]:
        product_filter = "AND sol.product_id = %s" if product_id else ""
        params: tuple[Any, ...] = (product_id,) if product_id else ()
        revenue = self._one(f"""
            SELECT COALESCE(SUM(sol.dispatched_qty * sol.unit_price * sol.exchange_rate), 0) AS revenue,
                   COALESCE(SUM(sol.dispatched_qty), 0) AS dispatched_qty
            FROM public.sales_order_lines sol WHERE sol.dispatched_qty > 0 {product_filter}
        """, params) or {}
        cost_filter = "WHERE product_id = %s" if product_id else ""
        cost = self._one(f"""
            SELECT COALESCE(SUM(received_qty * unit_price * exchange_rate) / NULLIF(SUM(received_qty), 0), 0) AS average_unit_cost
            FROM public.goods_receipt_lines {cost_filter}
        """, params) or {}
        revenue_value = Decimal(str(revenue.get("revenue", 0)))
        qty = Decimal(str(revenue.get("dispatched_qty", 0)))
        average_cost = Decimal(str(cost.get("average_unit_cost", 0)))
        total_cost = qty * average_cost
        margin = revenue_value - total_cost
        return {"agent": "financial", "product_id": product_id, "revenue": revenue_value, "cost": total_cost, "margin": margin,
                "margin_percent": (margin / revenue_value * 100) if revenue_value else Decimal("0"), "currency_basis": "historical_line_exchange_rate",
                "evidence": {"revenue_source": "sales_order_lines", "cost_source": "goods_receipt_lines", "dispatched_qty": qty},
                "generated_at": datetime.now(timezone.utc).isoformat()}

    def competition(self, product_id: int, country: str = "ES") -> dict[str, Any]:
        product = self._product(product_id)
        cache = self._one("""
            SELECT payload, country, reference_url, queried_at, expires_at FROM public.external_data_cache
            WHERE source = 'serpapi' AND operation = 'google_shopping' AND cache_key LIKE %s
            ORDER BY queried_at DESC LIMIT 1
        """, (f"{product_id}:%",))
        if not cache:
            return {"agent": "competition", "product_id": product_id, "product_name": product["name_product"], "alerts": [],
                    "source": {"name": "serpapi", "available": False, "detail": "No hay datos comparables vigentes para este producto."}, "generated_at": datetime.now(timezone.utc).isoformat()}
        payload = cache["payload"] if isinstance(cache["payload"], dict) else json.loads(cache["payload"])
        offers = [{"merchant": item.get("source") or item.get("seller"), "price": item.get("extracted_price"), "currency": item.get("currency"), "url": item.get("link")}
                  for item in payload.get("shopping_results", [])[:12] if item.get("extracted_price") is not None]
        return {"agent": "competition", "product_id": product_id, "product_name": product["name_product"], "offers": offers,
                "source": {"name": "serpapi", "country": cache["country"] or country, "reference_url": cache["reference_url"], "queried_at": cache["queried_at"], "expires_at": cache["expires_at"], "stale": cache["expires_at"] < datetime.now(timezone.utc)},
                "generated_at": datetime.now(timezone.utc).isoformat()}

    def market_intelligence(self, term: str, country: str = "ES") -> dict[str, Any]:
        connector = get_connectors()["serpapi"]
        status = connector.status().to_dict()
        result: dict[str, Any] = {"agent": "market_intelligence", "term": term, "country": country.upper(), "source": status, "generated_at": datetime.now(timezone.utc).isoformat()}
        if not status["available"]:
            result["data"] = None
            return result
        try:
            raw = connector.trends(term, country)  # type: ignore[attr-defined]
            self._cache("google_trends", f"{term.lower()}:{country.upper()}", raw, country.upper(), raw.get("search_metadata", {}).get("json_endpoint"))
            result["data"] = {"interest_over_time": raw.get("interest_over_time", {}).get("timeline_data", []), "related_queries": raw.get("related_queries", []), "queried_at": datetime.now(timezone.utc).isoformat(), "reference_url": raw.get("search_metadata", {}).get("json_endpoint")}
        except ExternalSourceError as exc:
            result["source"] = {**status, "available": False, "detail": str(exc)}
            result["data"] = None
        return result

    def commercial_content(self, product_id: int, channel: str) -> dict[str, Any]:
        product = self._product(product_id)
        facts = {"name": product["name_product"], "description": product["description_product"], "supplier": product["supplier"], "channel": channel}
        try:
            ai = generate_ai(f"Redacta contenido para {channel} usando solo estos datos: {json.dumps(facts, default=str)}", "No inventes especificaciones, disponibilidad, precios ni promociones.")
            return {"agent": "commercial", "product_id": product_id, "channel": channel, "content": ai["response"], "evidence": facts, "ai": {key: ai[key] for key in ("provider", "model", "used_fallback")}}
        except AIProviderError:
            return {"agent": "commercial", "product_id": product_id, "channel": channel, "content": f"{product['name_product']}. {product['description_product'] or ''}".strip(), "evidence": facts, "ai": None}

    def support_answer(self, question: str, product_id: int | None = None) -> dict[str, Any]:
        documents = self._all("""
            SELECT title, content, source, expires_at FROM public.knowledge_documents
            WHERE is_active = TRUE AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
              AND (to_tsvector('simple', title || ' ' || content) @@ plainto_tsquery('simple', %s) OR content ILIKE %s)
            ORDER BY updated_at DESC LIMIT 5
        """, (question, f"%{question[:80]}%"))
        stock: list[dict[str, Any]] = []
        product_context: dict[str, Any] | None = None
        if product_id:
            product_context = self._product(product_id)
            stock = self._all("""SELECT w.name AS warehouse, s.physical_qty - s.reserved_qty AS available_qty, u.code AS unit
                FROM public.inventory_stock_levels s JOIN public.inventory_warehouses w ON w.id = s.warehouse_id
                JOIN public.product_inventory_config c ON c.product_id = s.product_id JOIN public.inventory_units u ON u.id = c.base_unit_id
                WHERE s.product_id = %s""", (product_id,))
        context = {"documents": documents, "catalog_product": product_context, "stock": stock}
        fallback = "No hay informacion vigente suficiente para responder esa consulta."
        if stock:
            fallback = "Stock disponible confirmado: " + "; ".join(f"{row['warehouse']}: {row['available_qty']} {row['unit']}" for row in stock)
        try:
            ai = generate_ai(f"Pregunta: {question}\nContexto RAG: {json.dumps(context, default=str)}", "Responde solo con el contexto vigente. Si falta informacion, dilo claramente.")
            answer, ai_meta = ai["response"], {key: ai[key] for key in ("provider", "model", "used_fallback")}
        except AIProviderError:
            answer, ai_meta = fallback, None
        sources = [{"title": row["title"], "source": row["source"], "expires_at": row["expires_at"]} for row in documents]
        if product_context:
            sources.append({"title": product_context["name_product"], "source": "product_catalog", "expires_at": None})
        return {"agent": "customer_support", "answer": answer, "sources": sources, "stock": stock, "ai": ai_meta, "generated_at": datetime.now(timezone.utc).isoformat()}

    def risks(self) -> dict[str, Any]:
        rows = self._all("""
            SELECT p.pk_product AS product_id, TRIM(p.name_product) AS product_name,
                COALESCE(SUM(CASE WHEN m.movement_type = 'dispatch' THEN -m.quantity_signed ELSE 0 END), 0) AS dispatched_qty,
                COALESCE(SUM(CASE WHEN m.movement_type = 'return' THEN m.quantity_signed ELSE 0 END), 0) AS returned_qty
            FROM public.productos p LEFT JOIN public.inventory_movements m ON m.product_id = p.pk_product
            GROUP BY p.pk_product, p.name_product HAVING COALESCE(SUM(CASE WHEN m.movement_type = 'return' THEN m.quantity_signed ELSE 0 END), 0) > 0
            ORDER BY returned_qty DESC LIMIT 30
        """)
        alerts = []
        for row in rows:
            dispatched, returned = Decimal(str(row["dispatched_qty"])), Decimal(str(row["returned_qty"]))
            rate = returned / dispatched if dispatched else Decimal("0")
            if rate >= Decimal("0.1"):
                alerts.append({"type": "high_return_rate", "product_id": row["product_id"], "product_name": row["product_name"], "return_rate": rate, "evidence": {"returned_qty": returned, "dispatched_qty": dispatched}})
        return {"agent": "risks", "alerts": alerts, "source": "inventory_movements", "generated_at": datetime.now(timezone.utc).isoformat()}
