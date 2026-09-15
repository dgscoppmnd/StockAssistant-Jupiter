"""Persistent source files for future knowledge ingestion."""
import re
from pathlib import Path
from uuid import uuid4

from master_data_service import MasterDataError

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"
MAX_FILE_SIZE = 20 * 1024 * 1024
SUPPORTED_SUFFIXES = {".txt", ".pdf", ".md"}


def store_file(upload) -> Path:
    name = (upload.filename or "").replace("\\", "/").split("/")[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise MasterDataError("Solo se permiten archivos TXT, PDF y MD")
    safe_name = re.sub(r"[^\w. -]", "_", Path(name).stem)[:100] or "documento"
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    path = KNOWLEDGE_DIR / f"{uuid4().hex}_{safe_name}{suffix}"
    size = 0
    try:
        with path.open("xb") as output:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise MasterDataError("El archivo supera el limite de 20 MB", 413)
                output.write(chunk)
        if not size:
            raise MasterDataError("El archivo esta vacio")
        if suffix == ".pdf":
            with path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise MasterDataError("El archivo no tiene una cabecera PDF valida")
        else:
            try:
                text = path.read_text(encoding="utf-8-sig")
                if "\x00" in text:
                    raise ValueError("binary content")
            except (UnicodeError, ValueError) as exc:
                raise MasterDataError("TXT y MD deben contener texto UTF-8") from exc
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def save_document(service, values: dict, upload=None, record_id: int | None = None):
    # File references are assigned by the server, never supplied as arbitrary paths.
    values = dict(values)
    values.pop("archivo", None)
    if record_id is not None:
        service.get("knowledge-documents", record_id)
    service._values(service._definition("knowledge-documents"), values, creating=record_id is None)
    path = store_file(upload) if upload is not None else None
    if path:
        values["archivo"] = path.name
    try:
        if record_id is None:
            return service.create("knowledge-documents", values)
        return service.update("knowledge-documents", record_id, values)
    except Exception:
        if path:
            path.unlink(missing_ok=True)
        raise
