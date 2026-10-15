from __future__ import annotations

from datetime import datetime, timezone
import os
import threading
import logging
from fastapi.encoders import jsonable_encoder
from typing import Any, Callable

from psycopg2.extras import Json, RealDictCursor

from agent_service import AgentService
from commercial_agent_service import CommercialAgentService
from automation_service import AutomationService


class ExecutiveService:
    """Coordinates read-only agents; it never invokes inventory or purchase mutations."""

    def __init__(self, connection: Any):
        self.connection = connection
        self.inventory = AgentService(connection)
        self.commercial = CommercialAgentService(connection)

    def _all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def _one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._all(query, params)
        return rows[0] if rows else None

    def _record_decision(self, requested_agent: str | None, routed_agent: str, request_data: dict[str, Any], response: dict[str, Any]) -> int:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                INSERT INTO public.agent_decisions (requested_agent, routed_agent, request_data, response_summary)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (requested_agent, routed_agent, Json(request_data), Json(jsonable_encoder(response))))
            decision_id = int(cursor.fetchone()["id"])
        self.connection.commit()
        return decision_id

    def execute(
        self,
        question: str,
        product_id: int | None = None,
        agent: str | None = None,
        client_id: int | None = None,
    ) -> dict[str, Any]:
        lowered = question.lower()
        requested = (agent or "auto").strip().lower()
        if requested == "auto":
            if any(word in lowered for word in ("riesgo", "devoluci", "obsoleto")):
                routed = "risks"
            elif any(word in lowered for word in ("margen", "beneficio", "financ")):
                routed = "financial"
            elif any(word in lowered for word in ("tendencia", "mercado", "viral")):
                routed = "market_intelligence"
            elif any(word in lowered for word in ("competencia", "competidor", "precio externo")):
                routed = "competition"
            elif any(word in lowered for word in ("venta", "previsi", "demanda")):
                routed = "sales_forecast"
            elif any(word in lowered for word in ("compra", "proveedor", "reponer")):
                routed = "purchasing"
            elif any(word in lowered for word in ("stock", "bodega", "inventario")):
                routed = "stock"
            elif any(word in lowered for word in ("cliente", "cuenta", "ticket", "incidencia", "postventa")):
                routed = "clients"
            else:
                routed = "customer_support"
        else:
            routed = requested

        if routed == "clients":
            result = self.inventory.client_support(question, client_id)
        elif routed == "stock":
            result = self.inventory.stock_alerts()
        elif routed == "purchasing":
            result = self.inventory.purchase_recommendation(product_id) if product_id else self.inventory.stock_alerts()
        elif routed == "sales_forecast":
            if not product_id:
                raise ValueError("El agente de prediccion requiere product_id")
            result = self.commercial.sales_forecast(product_id)
        elif routed == "financial":
            result = self.commercial.financial_summary(product_id)
        elif routed == "competition":
            if not product_id:
                raise ValueError("El agente de competencia requiere product_id")
            result = self.commercial.competition(product_id)
        elif routed == "market_intelligence":
            result = self.commercial.market_intelligence(question)
        elif routed == "risks":
            result = self.commercial.risks()
        elif routed == "customer_support":
            result = self.commercial.support_answer(question, product_id)
        else:
            raise ValueError("Agente no disponible")

        decision_id = self._record_decision(agent, routed, {"question": question, "product_id": product_id}, result)
        return {"decision_id": decision_id, 
                "agent": "executive", 
                "routed_agent": routed, 
                "tool": result.get("agent", routed),
                "result": result, 
                "execution_policy": "read_only; no crea pedidos ni modifica inventario",
                "created_at": datetime.now(timezone.utc).isoformat()}

    def decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._all("SELECT id, requested_agent, routed_agent, request_data, response_summary, created_at FROM public.agent_decisions ORDER BY id DESC LIMIT %s", (limit,))


_worker_stop = threading.Event()
_worker_started = False
_worker_thread: threading.Thread | None = None


def start_automation_worker(connection_factory: Callable[[], Any]) -> None:
    global _worker_started, _worker_thread
    if _worker_started or os.getenv("AUTOMATION_WORKER_ENABLED", "true").lower() != "true":
        return
    _worker_stop.clear()
    _worker_started = True
    interval = max(int(os.getenv("AUTOMATION_WORKER_POLL_SECONDS", "60")), 15)

    def worker() -> None:
        while not _worker_stop.wait(interval):
            try:
                connection = connection_factory()
                try:
                    AutomationService(connection).run_due_rules()
                finally:
                    connection.close()
            except Exception:
                logging.getLogger(__name__).exception("Automation worker failed")

    _worker_thread = threading.Thread(target=worker, name="stockassistant-automation-worker", daemon=True)
    _worker_thread.start()


def stop_automation_worker() -> None:
    global _worker_started
    _worker_stop.set()
    if _worker_thread is not None:
        _worker_thread.join(timeout=5)
    _worker_started = bool(_worker_thread and _worker_thread.is_alive())
