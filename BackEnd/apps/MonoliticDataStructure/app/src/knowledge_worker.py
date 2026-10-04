"""Recover pending uploads on startup without manual indexing commands."""
import logging
import threading

from knowledge_service import KnowledgeService
from knowledge_vectors import configured_embedding_spec, EmbeddingSpec, KnowledgeVectors

_wake = threading.Event()


def cleanup_retired_vectors(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id::text, provider, model FROM public.knowledge_vector_deletions LIMIT 512"
        )
        rows = cursor.fetchall()
    connection.commit()
    groups = {}
    for point_id, provider, model in rows:
        groups.setdefault(EmbeddingSpec(provider, model), []).append(point_id)
    for spec, ids in groups.items():
        KnowledgeVectors(spec).delete(ids)
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM public.knowledge_vector_deletions WHERE id = ANY(%s::uuid[])", (ids,)
            )
        connection.commit()


def notify_knowledge_worker():
    _wake.set()


def start_knowledge_worker(connection_factory):
    """Inicia el worker que recupera pendientes y reindexa perfiles desactualizados."""
    stop = threading.Event()

    def run():
        while not stop.is_set():
            _wake.clear()
            connection = None
            try:
                connection = connection_factory()
                try:
                    cleanup_retired_vectors(connection)
                except Exception:
                    connection.rollback()
                    logging.getLogger("api.knowledge").warning(
                        "event=knowledge_vector_cleanup_pending"
                    )
                with connection.cursor() as cursor:
                    requested_spec = configured_embedding_spec()
                    if requested_spec is None:
                        cursor.execute(
                            """UPDATE public.knowledge_documents d
                            SET index_status = 'pending', index_progress = 0, index_error = NULL
                            WHERE index_status = 'available' AND NOT EXISTS
                            (SELECT 1 FROM public.knowledge_chunks c WHERE c.document_id = d.id)"""
                        )
                    else:
                        cursor.execute(
                            """UPDATE public.knowledge_documents d
                            SET index_status = 'pending', index_progress = 0, index_error = NULL
                            WHERE index_status = 'available' AND NOT EXISTS
                            (SELECT 1 FROM public.knowledge_chunks c WHERE c.document_id = d.id
                             AND c.embedding_provider = %s AND c.embedding_model = %s)""",
                            (requested_spec.provider, requested_spec.model),
                        )
                    cursor.execute(
                        """SELECT id FROM public.knowledge_documents WHERE index_status IN ('pending', 'processing')
                        AND is_active AND (expires_at IS NULL OR expires_at > clock_timestamp()) ORDER BY id LIMIT 20"""
                    )
                    ids = [row[0] for row in cursor.fetchall()]
                connection.commit()
                for document_id in ids:
                    if stop.is_set():
                        break
                    KnowledgeService(connection).index(document_id)
            except Exception:
                logging.getLogger("api.knowledge").warning("event=knowledge_worker_unavailable")
            finally:
                if connection is not None:
                    connection.close()
            if stop.is_set():
                return
            _wake.wait(5)

    threading.Thread(target=run, name="jupiter-knowledge", daemon=True).start()
    return stop
