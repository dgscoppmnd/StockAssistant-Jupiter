"""Extracción híbrida de texto nativo y texto visible en imágenes PDF."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from knowledge_errors import KnowledgeError


OCRProgress = Callable[[int, int], None]


def _normalized_line(value: str) -> str:
    return re.sub(r"\W+", " ", value, flags=re.UNICODE).strip().casefold()


def merge_page_text(native_text: str, ocr_text: str) -> str:
    """Conserva el texto nativo y añade únicamente líneas nuevas detectadas por OCR."""
    native_text = native_text.strip()
    normalized_native = _normalized_line(native_text)
    additional_lines: list[str] = []
    seen_lines: set[str] = set()

    for raw_line in ocr_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        normalized = _normalized_line(line)
        if not normalized or normalized in seen_lines:
            continue
        seen_lines.add(normalized)
        # El renderizado incluye también la capa nativa; este filtro evita indexarla dos veces.
        if normalized_native and normalized in normalized_native:
            continue
        additional_lines.append(line)

    parts = [part for part in (native_text, "\n".join(additional_lines)) if part]
    return "\n".join(parts)


def _ocr_page(pdf_page) -> str:
    import pytesseract

    dpi = int(os.getenv("RAG_OCR_DPI", "200"))
    timeout = int(os.getenv("RAG_OCR_TIMEOUT_SECONDS", "45"))
    languages = os.getenv("RAG_OCR_LANGUAGES", "spa+eng").strip() or "spa+eng"
    bitmap = pdf_page.render(scale=dpi / 72)
    try:
        return pytesseract.image_to_string(bitmap.to_pil(), lang=languages, timeout=timeout)
    finally:
        bitmap.close()


def extract_pdf_pages(path: Path, on_progress: OCRProgress | None = None) -> list[tuple[int, str]]:
    """Extrae cada página combinando su capa de texto con OCR de todo lo visible."""
    from pypdf import PdfReader
    import pypdfium2 as pdfium

    reader = PdfReader(path)
    if reader.is_encrypted:
        raise KnowledgeError("El PDF está cifrado. Carga una versión sin contraseña.")
    if len(reader.pages) > 1000:
        raise KnowledgeError("El PDF supera el límite de 1000 páginas.")

    pdf = pdfium.PdfDocument(str(path))
    try:
        if len(pdf) != len(reader.pages):
            raise KnowledgeError("No se pudieron interpretar todas las páginas del PDF.")
        pages: list[tuple[int, str]] = []
        for index, native_page in enumerate(reader.pages):
            page_number = index + 1
            native_text = native_page.extract_text() or ""
            pdf_page = pdf[index]
            try:
                ocr_text = _ocr_page(pdf_page)
            except Exception as exc:
                # Fallar de forma explícita evita marcar como completo un PDF cuyas imágenes no se analizaron.
                raise KnowledgeError(
                    f"No se pudo aplicar OCR en la página {page_number}. Comprueba Tesseract y los idiomas configurados."
                ) from exc
            finally:
                pdf_page.close()
            pages.append((page_number, merge_page_text(native_text, ocr_text)))
            if on_progress:
                on_progress(page_number, len(reader.pages))
    finally:
        pdf.close()

    if not any(text.strip() for _, text in pages):
        raise KnowledgeError(
            "El PDF no contiene texto legible, ni siquiera después de aplicar OCR."
        )
    return pages
