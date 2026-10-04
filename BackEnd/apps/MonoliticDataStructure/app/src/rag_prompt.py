"""Construccion del prompt con evidencia recuperada."""

NO_INFORMATION_MESSAGE = (
    "No tengo información sobre ese tema en mi biblioteca. "
    "Si añades un documento que lo trate, podré ayudarte a responder tu pregunta."
)

NO_INFORMATION_INSTRUCTION = (
    "Si la evidencia no contiene información que responda la pregunta, "
    f'responde únicamente: "{NO_INFORMATION_MESSAGE}". '
    "En ese caso, no añadas secciones, listas ni citas. "
    "Si contiene la respuesta, conserva el esquema habitual de respuesta y sus citas."
)


def source_label(item: dict) -> str:
    page = f", p. {item['page']}" if item.get("page") else ""
    return f"Fuente: {item['source']}{page}"


def build_rag_prompt(question: str, evidence: list[dict]) -> str:
    sections = [f"{source_label(item)}\n{item['text']}" for item in evidence]
    context = "\n\n".join(sections)
    return f"Pregunta: {question}\n\nEvidencia:\n{context}"
