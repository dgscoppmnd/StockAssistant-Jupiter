"""Contexto y citas de la evidencia RAG para el agente de soporte."""

from typing import Any


def build_support_context(
    documents: list[dict[str, Any]],
    pdf_documents: list[dict[str, Any]],
    product: dict[str, Any] | None,
    stock: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "documents": documents,
        "pdf_documents": pdf_documents,
        "catalog_product": product,
        "stock": stock,
    }


def support_fallback(stock: list[dict[str, Any]]) -> str:
    if not stock:
        return "No hay informacion vigente suficiente para responder esa consulta."
    availability = "; ".join(
        f"{row['warehouse']}: {row['available_qty']} {row['unit']}" for row in stock
    )
    return f"Stock disponible confirmado: {availability}"


def support_sources(
    documents: list[dict[str, Any]],
    pdf_documents: list[dict[str, Any]],
    product: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    sources = [database_source(document) for document in documents]
    sources.extend(pdf_source(document) for document in pdf_documents)
    if product:
        sources.append({"title": product["name_product"], "source": "product_catalog", "expires_at": None})
    return sources


def database_source(document: dict[str, Any]) -> dict[str, Any]:
    return {"title": document["title"], "source": document["source"], "expires_at": document["expires_at"]}


def pdf_source(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": document["source"],
        "source": document["source"],
        "page": document.get("page"),
        "score": document["score"],
        "expires_at": None,
    }
