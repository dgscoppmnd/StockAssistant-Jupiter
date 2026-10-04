import pytest

from DataBaseManagement.dbConectionPostgres import get_db_memori
from chat_history_service import ChatHistoryService

from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.endpointsChat import (
    _authenticated_user_id,
    _service,
    ai_service,
    router,
)


class FakeChatHistoryService:
    def __init__(self):
        self.saved_exchange = None

    def list_conversations(self, user_id, limit=50, offset=0):
        return [
            {
                "id": 12,
                "agent_key": "stockassistant",
                "title": "Consulta de stock",
                "message_count": 2,
            }
        ]

    def get_history(self, user_id, conversation_id, limit=100, offset=0):
        return {
            "conversation": {
                "id": conversation_id,
                "agent_key": "stockassistant",
                "title": "Consulta de stock",
            },
            "messages": [
                {
                    "id": 1,
                    "role": "user",
                    "content": "¿Qué productos tienen poco stock?",
                },
                {
                    "id": 2,
                    "role": "assistant",
                    "content": "Hay dos productos con poco stock.",
                },
            ],
        }

    def save_exchange(
        self,
        user_id,
        user_message,
        assistant_message,
        conversation_id=None,
        agent_key="stockassistant",
    ):
        self.saved_exchange = {
            "user_id": user_id,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "conversation_id": conversation_id,
            "agent_key": agent_key,
        }
        return {
            "conversation": {
                "id": conversation_id or 12,
                "agent_key": agent_key,
            },
            "messages": [],
        }


def create_test_client(service, user_id=7):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_authenticated_user_id] = lambda: user_id
    app.dependency_overrides[_service] = lambda: service
    return TestClient(app)


def test_chat_creates_conversation(monkeypatch):
    service = FakeChatHistoryService()
    client = create_test_client(service)

    monkeypatch.setattr(
        ai_service,
        "generate_for_provider",
        lambda provider, prompt, system_prompt: {
            "response": "Respuesta de prueba",
            "provider": provider,
            "model": "test-model",
            "used_fallback": False,
        },
    )

    response = client.post(
        "/chat",
        json={
            "prompt": "¿Cómo está el inventario?",
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == 12
    assert response.json()["response"] == "Respuesta de prueba"
    assert service.saved_exchange["user_id"] == 7
    assert service.saved_exchange["user_message"] == "¿Cómo está el inventario?"


def test_chat_uses_previous_history(monkeypatch):
    service = FakeChatHistoryService()
    client = create_test_client(service)
    received = {}

    def fake_generate(provider, prompt, system_prompt):
        received["prompt"] = prompt
        return {
            "response": "Respuesta con contexto",
            "provider": provider,
            "model": "test-model",
            "used_fallback": False,
        }

    monkeypatch.setattr(ai_service, "generate_for_provider", fake_generate)

    response = client.post(
        "/chat",
        json={
            "prompt": "¿Cuáles son?",
            "conversation_id": 12,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    assert "¿Qué productos tienen poco stock?" in received["prompt"]
    assert "¿Cuáles son?" in received["prompt"]
    assert service.saved_exchange["conversation_id"] == 12


def test_chat_history_lists_conversations():
    service = FakeChatHistoryService()
    client = create_test_client(service)

    response = client.get("/chat/history")

    assert response.status_code == 200
    assert response.json()["conversations"][0]["id"] == 12


def test_chat_history_returns_messages():
    service = FakeChatHistoryService()
    client = create_test_client(service)

    response = client.get(
        "/chat/history",
        params={"conversation_id": 12},
    )

    assert response.status_code == 200
    assert response.json()["conversation"]["id"] == 12
    assert len(response.json()["messages"]) == 2


def test_chat_history_requires_authentication():
    service = FakeChatHistoryService()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/chat/history")

    assert response.status_code == 401

def test_chat_history_persists_in_postgresql():
    database = get_db_memori()
    connection = next(database)
    conversation_id = None

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM public.users ORDER BY id LIMIT 1"
            )
            user = cursor.fetchone()

        if user is None:
            pytest.skip("No existe un usuario para probar el historial")

        user_id = int(user[0])
        service = ChatHistoryService(connection)

        saved = service.save_exchange(
            user_id=user_id,
            user_message="Mensaje real de prueba",
            assistant_message="Respuesta real de prueba",
            agent_key="test-chat-history",
        )
        conversation_id = int(saved["conversation"]["id"])

        history = service.get_history(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        assert history["conversation"]["id"] == conversation_id
        assert len(history["messages"]) == 2
        assert history["messages"][0]["role"] == "user"
        assert history["messages"][0]["content"] == "Mensaje real de prueba"
        assert history["messages"][1]["role"] == "assistant"
        assert history["messages"][1]["content"] == "Respuesta real de prueba"

        conversations = service.list_conversations(user_id=user_id)
        assert any(
            item["id"] == conversation_id
            for item in conversations
        )
    finally:
        if conversation_id is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM public.chat_conversations
                    WHERE id = %s
                    """,
                    (conversation_id,),
                )
            connection.commit()

        database.close()