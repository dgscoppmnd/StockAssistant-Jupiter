"""Compatibilidad y CLI del índice documental gestionado de Jupiter."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from types import SimpleNamespace

from DataBaseManagement.dbConectionPostgres import db_context
from knowledge_files import save_document
from knowledge_retrieval import retrieve_current
from knowledge_service import KnowledgeService
from master_data_service import MasterDataService

DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge"
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}


def search_knowledge(
    query: str, limit: int | None = None, source_type: str | None = None, zone: str | None = None
) -> list[dict]:
    evidence, _warnings = retrieve_current(
        query, limit=limit or 5, source_type=source_type, zone=zone
    )
    return evidence


def index_knowledge(directory: Path, batch_size: int = 16) -> int:
    """Importa archivos locales como registros y usa el mismo ciclo de la interfaz."""
    if not directory.is_dir():
        raise FileNotFoundError(f"No existe el directorio de conocimiento: {directory}")
    count = 0
    with db_context() as db:
        master = MasterDataService(db)
        index = KnowledgeService(db)
        existing = master.list("knowledge-documents")
        attached = {row.get("archivo") for row in existing}
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            # No vuelve a importar copias gestionadas ni archivos sustituidos.
            if path.name in attached or re.match(r"^[0-9a-f]{32}_", path.name):
                continue
            current = next((row for row in existing if row["source"] == path.name), None)
            values = {
                "title": path.stem,
                "content": f"Documento adjunto: {path.name}",
                "source": path.name,
            }
            with path.open("rb") as stream:
                upload = SimpleNamespace(filename=path.name, file=stream)
                record = save_document(master, values, upload, current["id"] if current else None)
            index.index(record["id"])
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM public.knowledge_chunks c JOIN public.knowledge_documents d "
                "ON d.id=c.document_id AND d.index_revision=c.revision WHERE d.index_status='available'"
            )
            count = cursor.fetchone()[0]
    return count


def main():
    parser = argparse.ArgumentParser(description="Importa conocimiento documental de Jupiter")
    parser.add_argument("--directory", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    args = parser.parse_args()
    print(f"Fragmentos disponibles: {index_knowledge(args.directory)}")


if __name__ == "__main__":
    main()
