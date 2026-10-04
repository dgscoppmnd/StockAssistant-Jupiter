"""Page-aware ingestion and authoritative, current evidence retrieval."""
import hashlib
import math
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from knowledge_files import MAX_FILE_SIZE, resolve_file
from knowledge_pdf import extract_pdf_pages
from knowledge_vectors import EmbeddingSpec, KnowledgeError, KnowledgeVectors, embed
from vector_store.knowledge_text import chunk_text


def document_pages(document, on_ocr_progress=None):
    """Extrae texto conservando páginas para que las respuestas puedan citar fuentes."""
    filename = document.get("archivo")
    if not filename:
        return [(None, document["content"])]
    try:
        path = resolve_file(filename)
    except ValueError as exc:
        raise KnowledgeError(str(exc)) from exc
    if path.stat().st_size > MAX_FILE_SIZE:
        raise KnowledgeError("El archivo supera el límite de 20 MiB.")
    if path.suffix.lower() == ".pdf":
        pages = extract_pdf_pages(path, on_ocr_progress)
    else:
        pages = [(None, path.read_text(encoding="utf-8-sig"))]
    if not any(text.strip() for _, text in pages):
        raise KnowledgeError("El archivo no contiene texto legible para indexar.")
    return pages


def split_pages(pages):
    chunks = []
    for page, text in pages:
        for content in chunk_text(text, chunk_size=900, overlap=120):
            chunks.append({"id": str(uuid4()), "page": page, "content": content})
            if len(chunks) > 5000:
                raise KnowledgeError("El documento supera el límite de 5000 fragmentos.")
    if not chunks:
        raise KnowledgeError("No hay texto para indexar.")
    return chunks


def indexing_progress(completed_batches: int, total_batches: int) -> int:
    """Calcula progreso por lotes y reserva el tramo final para confirmar la BD."""
    if total_batches <= 0:
        return 10
    completed = min(max(completed_batches, 0), total_batches)
    return min(95, 10 + math.floor(85 * completed / total_batches))


class KnowledgeService:
    """Coordina la ingesta documental y la recuperación de evidencia vigente."""

    def __init__(self, connection):
        self.connection = connection

    def index(self, document_id):
        """Bloquea por documento para evitar que dos workers lo indexen a la vez."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(92741, %s)", (document_id,))
            locked = cursor.fetchone()[0]
        self.connection.commit()
        if not locked:
            return
        try:
            self._index_locked(document_id)
        finally:
            self.connection.rollback()
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(92741, %s)", (document_id,))
            self.connection.commit()

    def _index_locked(self, document_id):
        """Extrae, fragmenta, vectoriza y publica atómicamente una revisión."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM public.knowledge_documents WHERE id = %s FOR UPDATE", (document_id,)
            )
            document = cursor.fetchone()
            if not document:
                return
            if document["index_status"] == "available":
                return
            revision = document["index_revision"]
            cursor.execute(
                """UPDATE public.knowledge_documents
                SET index_status = 'processing', index_progress = 2, index_error = NULL
                WHERE id = %s""",
                (document_id,),
            )
        self.connection.commit()
        chunks = []
        spec = None
        try:
            # El primer 10 % refleja extracción y OCR; el resto corresponde a embeddings.
            def report_ocr_progress(completed_pages: int, total_pages: int) -> None:
                progress = 2 + math.floor(8 * completed_pages / max(total_pages, 1))
                self._set_progress(document_id, revision, min(progress, 10))

            chunks = split_pages(document_pages(document, report_ocr_progress))
            digest = hashlib.sha256("\n".join(c["content"] for c in chunks).encode()).hexdigest()
            self._set_progress(document_id, revision, 10)
            first_batch = chunks[:16]
            first_vectors, spec = embed([chunk["content"] for chunk in first_batch])
            store = KnowledgeVectors(spec)
            store.upsert(
                [
                    {"id": chunk["id"], "vector": vector}
                    for chunk, vector in zip(first_batch, first_vectors)
                ]
            )
            total_batches = math.ceil(len(chunks) / 16)
            self._set_progress(document_id, revision, indexing_progress(1, total_batches))
            for start in range(16, len(chunks), 16):
                batch = chunks[start : start + 16]
                vectors, _ = embed([chunk["content"] for chunk in batch], spec)
                store.upsert(
                    [{"id": chunk["id"], "vector": vector} for chunk, vector in zip(batch, vectors)]
                )
                self._set_progress(
                    document_id, revision, indexing_progress(start // 16 + 1, total_batches)
                )
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM public.knowledge_documents WHERE id = %s AND index_revision = %s FOR UPDATE",
                    (document_id, revision),
                )
                if not cursor.fetchone():
                    self.connection.rollback()
                    self._retire_staged(chunks, spec)
                    return
                cursor.execute(
                    "DELETE FROM public.knowledge_chunks WHERE document_id = %s", (document_id,)
                )
                cursor.executemany(
                    "INSERT INTO public.knowledge_chunks (id, document_id, revision, page, content, embedding_provider, embedding_model) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    [
                        (
                            chunk["id"],
                            document_id,
                            revision,
                            chunk["page"],
                            chunk["content"],
                            spec.provider,
                            spec.model,
                        )
                        for chunk in chunks
                    ],
                )
                cursor.execute(
                    """UPDATE public.knowledge_documents
                    SET index_status = 'available', index_progress = 100, content_hash = %s, index_error = NULL,
                        index_embedding_provider = %s, index_embedding_model = %s
                    WHERE id = %s""",
                    (digest, spec.provider, spec.model, document_id),
                )
            self.connection.commit()
        except Exception as exc:
            self.connection.rollback()
            self._retire_staged(chunks, spec)
            message = (
                str(exc)
                if isinstance(exc, KnowledgeError)
                else "No se pudo extraer o indexar el documento. Comprueba el archivo y las dependencias PDF."
            )
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE public.knowledge_documents
                    SET index_status = 'error', index_error = %s
                    WHERE id = %s AND index_revision = %s""",
                    (message, document_id, revision),
                )
            self.connection.commit()

    def _retire_staged(self, chunks, spec):
        """Deja limpieza durable de vectores de revisiones no publicadas."""
        if spec is None:
            return
        with self.connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO public.knowledge_vector_deletions (id, provider, model) "
                "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                [(chunk["id"], spec.provider, spec.model) for chunk in chunks],
            )
        self.connection.commit()

    def _set_progress(self, document_id: int, revision: int, progress: int) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """UPDATE public.knowledge_documents
                SET index_progress = %s
                WHERE id = %s AND index_revision = %s AND index_status = 'processing'""",
                (progress, document_id, revision),
            )
        self.connection.commit()

    def available_chunks(self, ids=None):
        """Devuelve metadatos de chunks activos, vigentes y de la revisión actual."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            selected = " AND c.id = ANY(%s::uuid[])" if ids is not None else ""
            params = (ids,) if ids is not None else ()
            cursor.execute(
                """SELECT c.id::text AS id, c.document_id, c.page, c.content,
                c.embedding_provider, c.embedding_model,
                d.title, d.source, d.expires_at, d.archivo
                FROM public.knowledge_chunks c
                    JOIN public.knowledge_documents d
                    ON d.id = c.document_id
                WHERE d.is_active
                    AND (d.expires_at IS NULL OR d.expires_at > clock_timestamp())
                    AND d.index_status = 'available'
                    AND d.index_revision = c.revision"""
                + selected,
                params,
            )
            return {row["id"]: dict(row) for row in cursor.fetchall()}

    def retrieve(self, question, limit=8):
        """Busca evidencia por similitud y revalida vigencia tras consultar Qdrant."""
        rows = self.available_chunks()
        groups: dict[EmbeddingSpec, list[str]] = {}
        for chunk_id, row in rows.items():
            spec = EmbeddingSpec(row["embedding_provider"], row["embedding_model"])
            groups.setdefault(spec, []).append(chunk_id)
        hits: list[dict] = []
        failures: list[str] = []
        for spec, ids in groups.items():
            try:
                query_vector, _ = embed([question], spec)
                hits.extend(KnowledgeVectors(spec).search(query_vector[0], ids))
            except KnowledgeError as exc:
                failures.append(f"{spec.identifier}: {exc}")
        if failures:
            raise KnowledgeError(
                "No se pudieron consultar todos los documentos vigentes: " + " ".join(failures)
            )
        hits.sort(key=lambda hit: hit["score"], reverse=True)
        hits = hits[:limit]
        # Re-read after the external call to exclude documents retired during retrieval.
        current = self.available_chunks([hit["id"] for hit in hits])
        return [
            {**current[hit["id"]], "citation": f"F{index + 1}", "score": hit["score"]}
            for index, hit in enumerate(hits)
            if hit["id"] in current
        ]

    def status(self):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT
                id, title, archivo, index_status, index_progress, index_error, index_embedding_provider,
                index_embedding_model, (SELECT COUNT(*) FROM public.knowledge_chunks c
                  WHERE c.document_id = d.id AND c.revision = d.index_revision) AS chunk_count
                FROM public.knowledge_documents d
                WHERE is_active
                    AND (expires_at IS NULL OR expires_at > clock_timestamp())
                ORDER BY id"""
            )
            documents = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT COUNT(DISTINCT d.id) AS total
                FROM public.knowledge_documents d
                JOIN public.knowledge_chunks c
                    ON c.document_id = d.id AND c.revision = d.index_revision
                WHERE d.is_active
                    AND (d.expires_at IS NULL OR d.expires_at > clock_timestamp())
                    AND d.index_status = 'available'"""
            )
            available = cursor.fetchone()["total"]
        return {"available_documents": available, "documents": documents}
