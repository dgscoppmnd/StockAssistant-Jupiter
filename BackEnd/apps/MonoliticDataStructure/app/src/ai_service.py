from __future__ import annotations

from dataclasses import dataclass
from copy import copy
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Any, Callable

import requests

logger = logging.getLogger("api.ai")


class AIProviderError(Exception):
    def __init__(self, message: str, *, provider: str, retryable: bool):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    used_fallback: bool
    usage: dict[str, Any] | None = None
    cost: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.text,
            "provider": self.provider,
            "model": self.model,
            "used_fallback": self.used_fallback,
            'usage': self.usage,
            'cost': self.cost,
        }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_openai_text(data: dict[str, Any]) -> str:
    direct_text = data.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    text_parts: list[str] = []
    output = data.get("output", [])
    if not isinstance(output, list):
        return ""

    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)

    return "\n".join(text_parts)


class AIService:
    def __init__(
        self,
        *,
        ollama_call: Callable[[str, str | None], dict[str, Any]] | None = None,
        openai_call: Callable[[str, str | None], dict[str, Any]] | None = None,
    ) -> None:
        self.provider_mode = os.getenv("AI_PROVIDER", "auto").strip().lower() or "auto"
        self.ollama_url = os.getenv(
            "OLLAMA_URL", "http://host.docker.internal:11434/api/generate"
        ).strip()
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b").strip() or "qwen3:14b"
        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        self.ollama_think = os.getenv("OLLAMA_THINK", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
        self.openai_timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.cooldown_seconds = int(os.getenv("OLLAMA_FAILURE_COOLDOWN_SECONDS", "60"))
        self._ollama_down_until: datetime | None = None
        self._ollama_call = ollama_call or self._call_ollama
        self._openai_call = openai_call or self._call_openai

    def _normalized_provider_mode(self) -> str:
        if self.provider_mode in {"openai", "ollama", "auto"}:
            return self.provider_mode
        return "auto"

    def _ollama_available(self) -> bool:
        return not self._ollama_down_until or _now_utc() >= self._ollama_down_until

    def _mark_ollama_down(self) -> None:
        self._ollama_down_until = _now_utc() + timedelta(seconds=self.cooldown_seconds)

    def _call_ollama(self, prompt: str, system: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "think": self.ollama_think,
        }
        if system:
            payload["system"] = system
        if getattr(self, 'max_output_tokens', None):
            payload['options'] = {'num_predict': self.max_output_tokens}

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=self.ollama_timeout)
        except requests.RequestException as exc:
            raise AIProviderError(
                "Cannot connect to Ollama", provider="ollama", retryable=True
            ) from exc

        if response.status_code == 404:
            raise AIProviderError(
                "Ollama model is not available", provider="ollama", retryable=True
            )
        if response.status_code == 429:
            raise AIProviderError(
                "Ollama is temporarily unavailable", provider="ollama", retryable=True
            )
        if response.status_code >= 500:
            raise AIProviderError("Ollama server error", provider="ollama", retryable=True)
        if response.status_code >= 400:
            raise AIProviderError("Ollama request rejected", provider="ollama", retryable=False)

        data = response.json()
        return {
            "response": data.get("response", ""),
            "model": data.get("model") or self.ollama_model,
            'usage': {'input_tokens': data.get('prompt_eval_count'), 'output_tokens': data.get('eval_count')}
                     if 'prompt_eval_count' in data or 'eval_count' in data else None,
        }

    def _call_openai(self, prompt: str, system: str | None) -> dict[str, Any]:
        if not self.openai_api_key:
            raise AIProviderError("OpenAI is not configured", provider="openai", retryable=False)

        payload = {
            "model": self.openai_model,
            "input": prompt,
        }
        if system:
            payload["instructions"] = system
        if getattr(self, 'max_output_tokens', None):
            payload['max_output_tokens'] = self.max_output_tokens

        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.openai_timeout,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                "Cannot connect to OpenAI", provider="openai", retryable=True
            ) from exc

        if response.status_code >= 500:
            raise AIProviderError("OpenAI server error", provider="openai", retryable=True)
        if response.status_code >= 400:
            logger.warning(
                "event=openai_rejected status=%s model=%s body=%s",
                response.status_code,
                self.openai_model,
                response.text[:500],
            )
            raise AIProviderError("OpenAI request rejected", provider="openai", retryable=False)

        data = response.json()
        text = _extract_openai_text(data)
        return {"response": text, "model": data.get("model") or self.openai_model, 'usage': data.get('usage')}

    def _generate_with_provider(
        self, provider: str, prompt: str, system: str | None = None
    ) -> AIResponse:
        if provider == "ollama":
            data = self._ollama_call(prompt, system)
            return AIResponse(
                text=data.get("response", ""),
                provider="ollama",
                model=data.get("model", self.ollama_model),
                used_fallback=False,
                usage=data.get('usage'),
            )
        if provider == "openai":
            data = self._openai_call(prompt, system)
            return AIResponse(
                text=data.get("response", ""),
                provider="openai",
                model=data.get("model", self.openai_model),
                used_fallback=False,
                usage=data.get('usage'),
            )
        raise ValueError(f"Unsupported provider: {provider}")

    def generate(self, prompt: str, system: str | None = None) -> AIResponse:
        provider = self._normalized_provider_mode()
        if provider == "ollama":
            return self._generate_with_provider("ollama", prompt, system)
        if provider == "openai":
            return self._generate_with_provider("openai", prompt, system)

        if self._ollama_available():
            try:
                return self._generate_with_provider("ollama", prompt, system)
            except AIProviderError as exc:
                if not exc.retryable:
                    raise
                self._mark_ollama_down()
                logger.warning(
                    "event=ollama_fallback reason=%s cooldown_seconds=%s",
                    str(exc),
                    self.cooldown_seconds,
                )

        data = self._generate_with_provider("openai", prompt, system)
        return AIResponse(
            text=data.text, provider=data.provider, model=data.model, used_fallback=True, usage=data.usage, cost=data.cost
        )

    def generate_for_provider(
        self, provider: str, prompt: str, system: str | None = None
    ) -> dict[str, Any]:
        return self._generate_with_provider(provider.strip().lower(), prompt, system).to_dict()

    def provider_status(self, provider: str) -> dict[str, Any]:
        normalized = provider.strip().lower()
        if normalized == "openai":
            return {
                "provider": "openai",
                "configured": bool(self.openai_api_key),
                "available": bool(self.openai_api_key),
                "model": self.openai_model,
            }
        if normalized == "ollama":
            cooldown_active = bool(self._ollama_down_until and _now_utc() < self._ollama_down_until)
            return {
                "provider": "ollama",
                "configured": True,
                "available": self._ollama_available(),
                "model": self.ollama_model,
                "cooldown_active": cooldown_active,
                "cooldown_until": self._ollama_down_until.isoformat()
                if self._ollama_down_until
                else None,
            }
        raise ValueError(f"Unsupported provider: {provider}")

    def status(self) -> dict[str, Any]:
        mode = self._normalized_provider_mode()
        primary_provider = "openai" if mode == "openai" else "ollama"
        fallback_provider = "ollama" if primary_provider == "openai" else "openai"
        return {
            "mode": mode,
            "preferred_provider": primary_provider,
            "fallback_provider": fallback_provider,
            "ollama_model": self.ollama_model,
            "openai_model": self.openai_model,
            "openai_configured": bool(self.openai_api_key),
            "ollama_cooldown_active": bool(
                self._ollama_down_until and _now_utc() < self._ollama_down_until
            ),
            "ollama_cooldown_until": self._ollama_down_until.isoformat()
            if self._ollama_down_until
            else None,
            "providers": {
                "openai": self.provider_status("openai"),
                "ollama": self.provider_status("ollama"),
            },
        }


_service = AIService()


def generate_ai(prompt: str, system: str | None = None, *, timeout_seconds: float | None = None,
                max_output_tokens: int | None = None, allow_paid: bool = True) -> dict[str, Any]:
    if timeout_seconds is None and max_output_tokens is None and allow_paid:
        return _service.generate(prompt, system).to_dict()
    # Per-call clone avoids changing timeouts or provider policy on concurrent requests.
    bounded = copy(_service)
    bounded._ollama_call = bounded._call_ollama if getattr(_service._ollama_call, '__self__', None) is _service else _service._ollama_call
    bounded._openai_call = bounded._call_openai if getattr(_service._openai_call, '__self__', None) is _service else _service._openai_call
    if timeout_seconds is not None:
        if timeout_seconds <= 0:
            raise AIProviderError('Cycle deadline exceeded', provider='policy', retryable=False)
        # Auto can try two providers; reserve half the remaining budget for each.
        share = timeout_seconds / (2 if bounded.provider_mode == 'auto' and allow_paid else 1)
        bounded.ollama_timeout = min(bounded.ollama_timeout, share)
        bounded.openai_timeout = min(bounded.openai_timeout, share)
    bounded.max_output_tokens = max_output_tokens
    if not allow_paid:
        bounded.provider_mode = 'ollama'
    return bounded.generate(prompt, system).to_dict()


def get_ai_status() -> dict[str, Any]:
    return _service.status()
