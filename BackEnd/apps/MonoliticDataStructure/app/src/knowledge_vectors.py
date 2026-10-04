"""Embedding providers and Qdrant collections for Jupiter's document knowledge."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import math
import os
from typing import Any

import requests

from knowledge_errors import KnowledgeError


logger = logging.getLogger("api.knowledge_vectors")


class EmbeddingProviderError(KnowledgeError):
    """Fallo de embeddings que indica proveedor y posibilidad de reintento."""

    def __init__(self, message: str, *, provider: str, retryable: bool):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


@dataclass(frozen=True)
class EmbeddingSpec:
    provider: str
    model: str

    @property
    def identifier(self) -> str:
        """Identifica el perfil para mantener separados índices incompatibles."""
        return f"{self.provider}:{self.model}"


def configured_embedding_provider() -> str:
    provider = os.getenv("RAG_EMBEDDING_PROVIDER", "local").strip().lower() or "local"
    if provider not in {"local", "auto", "ollama", "openai"}:
        raise KnowledgeError("RAG_EMBEDDING_PROVIDER debe ser local, auto, ollama u openai.")
    return provider


def ollama_embedding_spec() -> EmbeddingSpec:
    model = os.getenv(
        "RAG_OLLAMA_EMBEDDING_MODEL", os.getenv("RAG_EMBEDDING_MODEL", "embeddinggemma")
    ).strip()
    return EmbeddingSpec("ollama", model or "embeddinggemma")


def openai_embedding_spec() -> EmbeddingSpec:
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    return EmbeddingSpec("openai", model or "text-embedding-3-small")


def configured_embedding_spec() -> EmbeddingSpec | None:
    """Devuelve el perfil explícito o None cuando el modo automático debe decidir."""
    provider = configured_embedding_provider()
    if provider == "local":
        from api.config import settings

        return EmbeddingSpec("local", settings.EMBEDDING_MODEL)
    if provider == "ollama":
        return ollama_embedding_spec()
    if provider == "openai":
        return openai_embedding_spec()
    return None


def _embedding_timeout() -> float:
    try:
        timeout = float(os.getenv("RAG_EMBEDDING_TIMEOUT_SECONDS", "60"))
    except ValueError as exc:
        raise KnowledgeError("RAG_EMBEDDING_TIMEOUT_SECONDS debe ser un número positivo.") from exc
    if timeout <= 0:
        raise KnowledgeError("RAG_EMBEDDING_TIMEOUT_SECONDS debe ser un número positivo.")
    return timeout


def _ollama_embedding_url() -> str:
    base = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434/api/generate")
    return base.split("/api/", 1)[0].rstrip("/") + "/api/embed"


def _validate_vectors(vectors: Any, expected_count: int, provider: str) -> list[list[float]]:
    """Comprueba cantidad, dimensión y valores finitos antes de indexar vectores."""
    if not isinstance(vectors, list) or len(vectors) != expected_count or not vectors:
        raise EmbeddingProviderError(
            "El proveedor devolvió un número inválido de embeddings.",
            provider=provider,
            retryable=False,
        )
    dimension = len(vectors[0]) if isinstance(vectors[0], list) else 0
    if not dimension or any(
        not isinstance(vector, list)
        or len(vector) != dimension
        or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            for value in vector
        )
        or not any(vector)
        for vector in vectors
    ):
        raise EmbeddingProviderError(
            "El proveedor devolvió embeddings inválidos.", provider=provider, retryable=False
        )
    return [[float(value) for value in vector] for vector in vectors]


def _raise_for_embedding_status(response: requests.Response, provider: str) -> None:
    if response.status_code < 400:
        return
    retryable = response.status_code >= 500 or (
        provider == "ollama" and response.status_code == 404
    )
    if provider == "ollama" and response.status_code == 404:
        message = "Ollama no tiene disponible el endpoint o el modelo de embeddings configurado."
    elif response.status_code >= 500:
        message = f"El servidor de {provider} no está disponible para generar embeddings."
    else:
        message = f"{provider.capitalize()} rechazó la solicitud de embeddings (HTTP {response.status_code})."
    raise EmbeddingProviderError(message, provider=provider, retryable=retryable)


def _embed_with_ollama(texts: list[str], spec: EmbeddingSpec) -> list[list[float]]:
    try:
        response = requests.post(
            _ollama_embedding_url(),
            json={"model": spec.model, "input": texts, "truncate": False},
            timeout=(5, _embedding_timeout()),
        )
    except requests.RequestException as exc:
        raise EmbeddingProviderError(
            "No se pudo conectar con Ollama para generar embeddings.",
            provider="ollama",
            retryable=True,
        ) from exc
    _raise_for_embedding_status(response, "ollama")
    try:
        return _validate_vectors(response.json()["embeddings"], len(texts), "ollama")
    except (KeyError, TypeError, ValueError) as exc:
        raise EmbeddingProviderError(
            "Ollama devolvió una respuesta de embeddings no válida.",
            provider="ollama",
            retryable=False,
        ) from exc


def _embed_with_openai(texts: list[str], spec: EmbeddingSpec) -> list[list[float]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise EmbeddingProviderError(
            "OpenAI embeddings no está configurado.", provider="openai", retryable=False
        )
    try:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": spec.model, "input": texts, "encoding_format": "float"},
            timeout=(5, _embedding_timeout()),
        )
    except requests.RequestException as exc:
        raise EmbeddingProviderError(
            "No se pudo conectar con OpenAI para generar embeddings.",
            provider="openai",
            retryable=True,
        ) from exc
    _raise_for_embedding_status(response, "openai")
    try:
        items = sorted(response.json()["data"], key=lambda item: item["index"])
        if [item["index"] for item in items] != list(range(len(texts))):
            raise ValueError()
        return _validate_vectors([item["embedding"] for item in items], len(texts), "openai")
    except (KeyError, TypeError, ValueError) as exc:
        raise EmbeddingProviderError(
            "OpenAI devolvió una respuesta de embeddings no válida.",
            provider="openai",
            retryable=False,
        ) from exc


def _embed_with_spec(texts: list[str], spec: EmbeddingSpec) -> list[list[float]]:
    if spec.provider == "ollama":
        return _embed_with_ollama(texts, spec)
    if spec.provider == "openai":
        return _embed_with_openai(texts, spec)
    if spec.provider == "local":
        from api.config import settings
        from vector_store.embeddings import encode_texts

        if spec.model != settings.EMBEDDING_MODEL:
            raise KnowledgeError("El modelo local ha cambiado; reindexa los documentos.")
        return _validate_vectors(encode_texts(texts), len(texts), "local")
    raise KnowledgeError("El proveedor de embeddings del documento no es compatible.")


def embed(
    texts: list[str], spec: EmbeddingSpec | None = None
) -> tuple[list[list[float]], EmbeddingSpec]:
    """Genera vectores; en modo auto usa Ollama y recurre a OpenAI si es reintentable."""
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise KnowledgeError("No se puede generar un embedding de texto vacío.")
    if spec is not None:
        return _embed_with_spec(texts, spec), spec

    provider = configured_embedding_provider()
    if provider == "local":
        selected = configured_embedding_spec()
        return _embed_with_spec(texts, selected), selected
    if provider == "ollama":
        selected = ollama_embedding_spec()
        return _embed_with_spec(texts, selected), selected
    if provider == "openai":
        selected = openai_embedding_spec()
        return _embed_with_spec(texts, selected), selected

    local_spec = ollama_embedding_spec()
    try:
        return _embed_with_spec(texts, local_spec), local_spec
    except EmbeddingProviderError as exc:
        if not exc.retryable:
            raise
        logger.warning("event=rag_embedding_fallback provider=ollama reason=%s", exc)
        cloud_spec = openai_embedding_spec()
        try:
            return _embed_with_spec(texts, cloud_spec), cloud_spec
        except EmbeddingProviderError as fallback_error:
            raise KnowledgeError(
                f"{exc} Respaldo OpenAI no disponible: {fallback_error}"
            ) from fallback_error


class KnowledgeVectors:
    """Acceso a la colección Qdrant de chunks documentales para un perfil de embedding."""

    def __init__(self, spec: EmbeddingSpec):
        self.url = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
        self.spec = spec
        collection_hash = hashlib.sha256(spec.identifier.encode("utf-8")).hexdigest()[:16]
        self.collection = f"jupiter_documents_{collection_hash}"

    def request(
        self,
        method: str,
        path: str = "",
        payload: dict[str, Any] | None = None,
        allow_missing: bool = False,
    ):
        try:
            response = requests.request(
                method,
                f"{self.url}/collections/{self.collection}{path}",
                json=payload,
                headers={"api-key": os.getenv("QDRANT_API_KEY", "")},
                timeout=(5, 30),
            )
            if allow_missing and response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()["result"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise KnowledgeError("El índice semántico Qdrant no está disponible.") from exc

    def upsert(self, points: list[dict[str, Any]]) -> None:
        if not points:
            return
        _validate_vectors([point["vector"] for point in points], len(points), self.spec.provider)
        if self.request("GET", allow_missing=True) is None:
            try:
                self.request(
                    "PUT",
                    payload={"vectors": {"size": len(points[0]["vector"]), "distance": "Cosine"}},
                )
            except KnowledgeError:
                self.request("GET")
        self.request("PUT", "/points?wait=true", {"points": points})

    def delete(self, ids: list[str]) -> None:
        if ids and self.request("GET", allow_missing=True) is not None:
            self.request("POST", "/points/delete?wait=true", {"points": ids})

    def search(self, query_vector: list[float], ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        result = self.request(
            "POST",
            "/points/query",
            {
                "query": query_vector,
                "filter": {"must": [{"has_id": ids}]},
                "limit": 8,
                "score_threshold": float(os.getenv("RAG_MIN_SCORE", "0.5")),
                "with_payload": False,
            },
        )
        return result["points"]
