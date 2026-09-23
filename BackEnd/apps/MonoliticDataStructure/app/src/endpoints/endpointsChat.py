from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from DataBaseManagement.dbConectionPostgres import get_db_memori
from DataBaseManagement.schemasChat import ChatRequest
from ai_service import AIProviderError, AIService
from chat_history_service import ChatHistoryError, ChatHistoryService
from ollama_service import get_system_prompt
from security import extract_bearer_token, verify_session_token


router = APIRouter(prefix="/chat", tags=["chat"])
ai_service = AIService()


def _service(db=Depends(get_db_memori)) -> ChatHistoryService:
    return ChatHistoryService(db)


def _authenticated_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> int:
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session token",
        )

    claims = verify_session_token(token)
    if claims is None or claims.get("user_id") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )

    try:
        return int(claims["user_id"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session user",
        ) from exc


def _raise_history_error(exc: ChatHistoryError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=str(exc),
    ) from exc


def _build_conversation_prompt(
    messages: list[dict[str, Any]],
    current_prompt: str,
) -> str:
    if not messages:
        return current_prompt

    history_lines: list[str] = []
    for message in messages:
        label = "Usuario" if message["role"] == "user" else "Asistente"
        history_lines.append(f"{label}: {message['content']}")

    history_text = "\n".join(history_lines)
    return (
        "Continúa la conversación teniendo en cuenta este historial:\n\n"
        f"{history_text}\n\n"
        f"Usuario: {current_prompt}"
    )


@router.post("")
def chat(
    payload: ChatRequest,
    user_id: int = Depends(_authenticated_user_id),
    service: ChatHistoryService = Depends(_service),
):
    previous_messages: list[dict[str, Any]] = []

    if payload.conversation_id is not None:
        try:
            history = service.get_history(
                user_id=user_id,
                conversation_id=payload.conversation_id,
                limit=20,
            )
        except ChatHistoryError as exc:
            _raise_history_error(exc)
        previous_messages = history["messages"]

    llm_prompt = _build_conversation_prompt(
        previous_messages,
        payload.prompt.strip(),
    )
    system_prompt = (
        get_system_prompt()
        + " Mantén la continuidad de la conversación y responde en español."
    )

    try:
        result = ai_service.generate_for_provider(
            payload.provider,
            llm_prompt,
            system_prompt,
        )
    except AIProviderError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.retryable
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    response_text = str(result.get("response") or "").strip()
    if not response_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El proveedor de IA devolvió una respuesta vacía",
        )

    try:
        saved = service.save_exchange(
            user_id=user_id,
            user_message=payload.prompt,
            assistant_message=response_text,
            conversation_id=payload.conversation_id,
            agent_key=payload.agent_key,
        )
    except ChatHistoryError as exc:
        _raise_history_error(exc)

    return {
        **result,
        "conversation_id": saved["conversation"]["id"],
    }


@router.get("/history")
def chat_history(
    conversation_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(_authenticated_user_id),
    service: ChatHistoryService = Depends(_service),
):
    try:
        if conversation_id is not None:
            return service.get_history(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
                offset=offset,
            )

        return {
            "conversations": service.list_conversations(
                user_id=user_id,
                limit=limit,
                offset=offset,
            )
        }
    except ChatHistoryError as exc:
        _raise_history_error(exc)