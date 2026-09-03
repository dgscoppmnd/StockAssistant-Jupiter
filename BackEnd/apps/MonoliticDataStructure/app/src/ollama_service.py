from datetime import datetime

from fastapi import HTTPException

from ai_service import AIProviderError, generate_ai

MODEL = "provider-managed"
SYSTEM_PROMPT = """Tu nombre es StockAssistant,
eres una asistente virtual que ayuda a los usuarios a analizar.
Siempre debes responder en español y proporcionar respuestas claras y concisas."""


def get_system_prompt() -> str:
    current_datetime = datetime.now().astimezone()
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    return f"{SYSTEM_PROMPT} La fecha, hora y zona horaria actual del sistema es: {formatted_datetime}."


def generate_with_ollama(prompt: str, system: str | None = None):
    try:
        return generate_ai(prompt, system=system)
    except AIProviderError as exc:
        if exc.retryable:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
