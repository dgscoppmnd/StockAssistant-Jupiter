from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
import threading
import logging
from fastapi.encoders import jsonable_encoder
from typing import Any, Callable

from psycopg2.extras import Json, RealDictCursor

from agent_service import AgentService
from commercial_agent_service import CommercialAgentService


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

    def execute(self, question: str, product_id: int | None = None, agent: str | None = None) -> dict[str, Any]:
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
            else:
                routed = "customer_support"
        else:
            routed = requested

        if routed == "stock":
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
        return {"decision_id": decision_id, "agent": "executive", "routed_agent": routed, "tool": result.get("agent", routed),
                "result": result, "execution_policy": "read_only; no crea pedidos ni modifica inventario", "created_at": datetime.now(timezone.utc).isoformat()}

    def decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._all("SELECT id, requested_agent, routed_agent, request_data, response_summary, created_at FROM public.agent_decisions ORDER BY id DESC LIMIT %s", (limit,))


class AutomationService(ExecutiveService):
    DEFAULT_RULES = (
        ("stock_reorder_proposals", "Propuestas de reposicion", "Genera propuestas pendientes de aprobacion humana a partir de stock bajo."),
        ("daily_inventory_report", "Informe diario", "Genera un informe de inventario y movimientos del ultimo dia."),
        ("risk_alerts", "Alertas de riesgos", "Registra las alertas de riesgo basadas en datos confirmados."),
    )

    def ensure_default_rules(self) -> None:
        with self.connection.cursor() as cursor:
            for code, name, description in self.DEFAULT_RULES:
                cursor.execute("""INSERT INTO public.automation_rules (code, name, description, is_active, interval_minutes)
                    VALUES (%s, %s, %s, FALSE, 1440) ON CONFLICT (code) DO NOTHING""", (code, name, description))
        self.connection.commit()

    def rules(self) -> list[dict[str, Any]]:
        self.ensure_default_rules()
        return self._all("SELECT id, code, name, description, is_active, interval_minutes, last_run_at, created_at, updated_at FROM public.automation_rules ORDER BY id")

    def set_rule_active(self, rule_id: int, is_active: bool) -> dict[str, Any]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("UPDATE public.automation_rules SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING *", (is_active, rule_id))
            rule = cursor.fetchone()
        self.connection.commit()
        if not rule:
            raise ValueError("Automatizacion no encontrada")
        return dict(rule)

    def _create_reorder_proposals(self, run_id: int) -> dict[str, Any]:
        alerts = self.inventory.stock_alerts()["alerts"]
        created = 0
        with self.connection.cursor() as cursor:
            for alert in alerts:
                cursor.execute("""
                    INSERT INTO public.purchase_proposals (automation_run_id, product_id, warehouse_id, suggested_qty, base_unit_code, status, justification)
                    SELECT %s, %s, %s, %s, %s, 'pending_approval', %s
                    WHERE NOT EXISTS (SELECT 1 FROM public.purchase_proposals WHERE product_id = %s AND warehouse_id = %s AND status = 'pending_approval')
                """, (run_id, alert["product_id"], alert["warehouse_id"], alert["reorder_quantity"], alert["base_unit_code"],
                      "Stock disponible bajo el punto de pedido; requiere aprobacion humana.", alert["product_id"], alert["warehouse_id"]))
                created += cursor.rowcount
        return {"source": "stock_alerts", "alerts": len(alerts), "created_pending_approval": created}

    def _daily_report(self) -> dict[str, Any]:
        return self._one("""
            SELECT COUNT(*) AS movements_24h, COALESCE(SUM(quantity_signed), 0) AS net_quantity_24h
            FROM public.inventory_movements WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
        """) or {}

    def run_rule(self, rule_id: int, initiated_by: str = "manual") -> dict[str, Any]:
        rule = self._one("SELECT * FROM public.automation_rules WHERE id = %s", (rule_id,))
        if not rule:
            raise ValueError("Automatizacion no encontrada")
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("INSERT INTO public.automation_runs (rule_id, initiated_by, status) VALUES (%s, %s, 'running') RETURNING id", (rule_id, initiated_by))
            run_id = int(cursor.fetchone()["id"])
        self.connection.commit()
        try:
            if rule["code"] == "stock_reorder_proposals":
                result = self._create_reorder_proposals(run_id)
            elif rule["code"] == "daily_inventory_report":
                result = self._daily_report()
            else:
                result = self.commercial.risks()
            with self.connection.cursor() as cursor:
                cursor.execute("UPDATE public.automation_runs SET status = 'completed', result = %s, completed_at = CURRENT_TIMESTAMP WHERE id = %s", (Json(jsonable_encoder(result)), run_id))
                cursor.execute("UPDATE public.automation_rules SET last_run_at = CURRENT_TIMESTAMP WHERE id = %s", (rule_id,))
            self.connection.commit()
            return {"run_id": run_id, "rule": rule["code"], "status": "completed", "result": result}
        except Exception as exc:
            self.connection.rollback()
            with self.connection.cursor() as cursor:
                cursor.execute("UPDATE public.automation_runs SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP WHERE id = %s", (str(exc)[:500], run_id))
            self.connection.commit()
            raise

    def run_due_rules(self) -> list[dict[str, Any]]:
        self.ensure_default_rules()
        due = self._all("""SELECT id FROM public.automation_rules WHERE is_active = TRUE
            AND (last_run_at IS NULL OR last_run_at + (interval_minutes * INTERVAL '1 minute') <= CURRENT_TIMESTAMP)""")
        return [self.run_rule(rule["id"], "scheduler") for rule in due]

    def runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._all("""SELECT r.id, a.code AS rule_code, r.initiated_by, r.status, r.result, r.error_message, r.started_at, r.completed_at
            FROM public.automation_runs r JOIN public.automation_rules a ON a.id = r.rule_id ORDER BY r.id DESC LIMIT %s""", (limit,))

    def proposals(self) -> list[dict[str, Any]]:
        return self._all("""SELECT p.id, p.product_id, TRIM(pr.name_product) AS product_name, p.warehouse_id, w.name AS warehouse_name,
            p.suggested_qty, p.base_unit_code, p.status, p.justification, p.created_at
            FROM public.purchase_proposals p JOIN public.productos pr ON pr.pk_product = p.product_id
            JOIN public.inventory_warehouses w ON w.id = p.warehouse_id ORDER BY p.id DESC""")


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
