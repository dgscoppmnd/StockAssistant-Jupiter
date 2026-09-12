from src.rag_prompt import build_rag_prompt
from src.vector_store.knowledge_text import chunk_text, normalize_text


def test_chunk_text_preserves_all_content():
    text = "Uno. Dos. Tres. Cuatro. Cinco."
    chunks = chunk_text(text, chunk_size=14, overlap=4)

    assert len(chunks) > 1
    assert "Uno." in chunks[0]
    assert "Cinco." in chunks[-1]


def test_chunk_text_rejects_invalid_overlap():
    try:
        chunk_text("texto", chunk_size=10, overlap=10)
    except ValueError as exc:
        assert "chunk_size" in str(exc)
    else:
        raise AssertionError("Se esperaba ValueError")


def test_build_rag_prompt_contains_page_citation_context():
    prompt = build_rag_prompt(
        "Que hace Qdrant?",
        [{"source": "guia.pdf", "page": 2, "text": "Qdrant recupera contexto."}],
    )

    assert "Fuente: guia.pdf, p. 2" in prompt
    assert "Qdrant recupera contexto." in prompt


def test_normalize_text_collapses_whitespace():
    assert normalize_text(" uno\n\t dos ") == "uno dos"
