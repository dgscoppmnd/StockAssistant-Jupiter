"""Construccion del prompt con evidencia recuperada."""


def source_label(item: dict) -> str:
    page = f", p. {item['page']}" if item.get("page") else ""
    return f"Fuente: {item['source']}{page}"


def build_rag_prompt(question: str, evidence: list[dict]) -> str:
    sections = [f"{source_label(item)}\n{item['text']}" for item in evidence]
    context = "\n\n".join(sections)
    return f"Pregunta: {question}\n\nEvidencia:\n{context}"
