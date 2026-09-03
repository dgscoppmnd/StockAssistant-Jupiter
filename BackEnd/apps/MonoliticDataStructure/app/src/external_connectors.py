from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import time
from typing import Any

import requests


class ExternalSourceError(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class SourceStatus:
    name: str
    available: bool
    mode: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ReadOnlyConnector:
    """Common, read-only connector contract used by inventory agents."""

    name = "unknown"

    def status(self) -> SourceStatus:
        raise NotImplementedError


class SerpApiConnector(ReadOnlyConnector):
    name = "serpapi"
    _blocked_until: datetime | None = None
    _last_request_at: datetime | None = None

    def __init__(self) -> None:
        self.api_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.timeout = float(os.getenv("SERPAPI_TIMEOUT_SECONDS", "10"))
        self.max_retries = int(os.getenv("SERPAPI_MAX_RETRIES", "2"))
        self.cooldown_seconds = int(os.getenv("SERPAPI_COOLDOWN_SECONDS", "60"))
        self.min_interval_seconds = float(os.getenv("SERPAPI_MIN_INTERVAL_SECONDS", "0.25"))

    def status(self) -> SourceStatus:
        if not self.api_key:
            return SourceStatus(self.name, False, "read_only", "No configurada: falta SERPAPI_API_KEY.")
        if type(self)._blocked_until and datetime.now(timezone.utc) < type(self)._blocked_until:
            return SourceStatus(self.name, False, "read_only", "En pausa temporal por cuota o error remoto.")
        return SourceStatus(self.name, True, "read_only", "Disponible para Google Shopping y Google Trends.")

    def _search(self, params: dict[str, str]) -> dict[str, Any]:
        if not self.api_key:
            raise ExternalSourceError("SerpAPI no esta configurada")
        if type(self)._blocked_until and datetime.now(timezone.utc) < type(self)._blocked_until:
            raise ExternalSourceError("SerpAPI esta temporalmente en pausa", retryable=True)

        previous = type(self)._last_request_at
        if previous:
            elapsed = (datetime.now(timezone.utc) - previous).total_seconds()
            if elapsed < self.min_interval_seconds:
                time.sleep(self.min_interval_seconds - elapsed)

        request_params = {**params, "api_key": self.api_key, "output": "json"}
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get("https://serpapi.com/search", params=request_params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise ExternalSourceError("No se pudo contactar SerpAPI", retryable=True) from exc
                time.sleep(0.25 * (2**attempt))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                type(self)._blocked_until = datetime.now(timezone.utc) + timedelta(seconds=self.cooldown_seconds)
                if attempt == self.max_retries:
                    raise ExternalSourceError("SerpAPI respondio con cuota agotada o error temporal", retryable=True)
                time.sleep(0.25 * (2**attempt))
                continue
            if response.status_code >= 400:
                raise ExternalSourceError("SerpAPI rechazo la consulta")
            type(self)._last_request_at = datetime.now(timezone.utc)
            return response.json()
        raise ExternalSourceError("No se pudo completar la consulta SerpAPI", retryable=True)

    def shopping(self, query: str, country: str, language: str) -> dict[str, Any]:
        return self._search({"engine": "google_shopping", "q": query, "gl": country.lower(), "hl": language.lower()})

    def trends(self, query: str, country: str) -> dict[str, Any]:
        return self._search({"engine": "google_trends", "q": query, "geo": country.upper()})


class CredentialGatedConnector(ReadOnlyConnector):
    def __init__(self, name: str, required_variables: tuple[str, ...]) -> None:
        self.name = name
        self.required_variables = required_variables

    def status(self) -> SourceStatus:
        missing = [key for key in self.required_variables if not os.getenv(key, "").strip()]
        if missing:
            return SourceStatus(self.name, False, "read_only", "No disponible: faltan credenciales o autorizacion oficial.")
        return SourceStatus(self.name, False, "read_only", "Credenciales detectadas; la integracion requiere activacion y validacion oficial.")


def get_connectors() -> dict[str, ReadOnlyConnector]:
    return {
        "serpapi": SerpApiConnector(),
        "aliexpress": CredentialGatedConnector("aliexpress", ("ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_REFRESH_TOKEN")),
        "amazon_sp_api": CredentialGatedConnector("amazon_sp_api", ("AMAZON_SP_API_CLIENT_ID", "AMAZON_SP_API_CLIENT_SECRET", "AMAZON_SP_API_REFRESH_TOKEN")),
    }
