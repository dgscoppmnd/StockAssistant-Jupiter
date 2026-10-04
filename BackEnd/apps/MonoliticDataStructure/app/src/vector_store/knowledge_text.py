"""Utilidades puras para normalizar y fragmentar conocimiento documental."""

import re


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size debe ser mayor que overlap")

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = find_chunk_end(clean, start, chunk_size)
        chunks.append(clean[start:end].strip())
        if end == len(clean):
            break
        start = end - overlap
    return chunks


def find_chunk_end(text: str, start: int, chunk_size: int) -> int:
    end = min(start + chunk_size, len(text))
    if end == len(text):
        return end
    split_at = text.rfind(". ", start, end)
    return split_at + 1 if split_at > start + chunk_size // 2 else end


def infer_zone(content: str) -> str:
    content_lower = content.lower()

    zones_keywords = {
        "analiticas": [
            "analítica",
            "analiticas",
            "dashboard",
            "informe",
            "tendencia",
            "kpi",
            "métrica",
            "metrica",
        ],
        "metricas": ["rendimiento", "desempeño", "conversión", "porcentaje", "tasa"],
        "logistica": ["logística", "logistica", "envío", "envio", "transporte", "distribución"],
        "inventario": [
            "inventario",
            "stock",
            "existencias",
            "almacenamiento",
            "restock",
            "reabastecimiento",
            "rotación",
            "mínimo requerido",
            "sku",
        ],
        "producto": ["catálogo", "catalogo", "categoría"],
        "ventas": ["facturación", "ingreso neto", "orden de compra", "transacción"],
        "proveedores": ["proveedor", "proveedores", "suministro", "abastecimiento"],
    }

    zone_scores = {}
    for zone, keywords in zones_keywords.items():
        score = 0
        for kw in keywords:
            matches = len(re.findall(rf"\b{re.escape(kw)}\b", content_lower))
            score += matches
        if score > 0:
            zone_scores[zone] = score

    if not zone_scores:
        return "general"

    sorted_zones = sorted(zone_scores.items(), key=lambda x: x[1], reverse=True)
    best_zone, best_score = sorted_zones[0]

    if best_score < 2:
        return "general"

    if len(sorted_zones) > 1:
        second_zone, second_score = sorted_zones[1]
        if (best_score - second_score < 2) and best_score < 5:
            return "general"

    return best_zone
