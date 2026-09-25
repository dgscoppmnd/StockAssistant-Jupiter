from __future__ import annotations

from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


class ChatHistoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class ChatHistoryService:
    def __init__(self, connection: Any):
        self.connection = connection

    def list_conversations(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.agent_key,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id)::INTEGER AS message_count
                FROM public.chat_conversations c
                LEFT JOIN public.chat_messages m
                    ON m.conversation_id = c.id
                WHERE c.user_id = %s
                GROUP BY c.id
                ORDER BY c.updated_at DESC, c.id DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_history(
        self,
        user_id: int,
        conversation_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, agent_key, title, created_at, updated_at
                FROM public.chat_conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
            conversation = cursor.fetchone()

            if not conversation:
                raise ChatHistoryError("Conversación no encontrada", 404)

            cursor.execute(
                """
                SELECT id, role, content, created_at
                FROM (
                    SELECT id, role, content, created_at
                    FROM public.chat_messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                ) AS recent_messages
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id, limit, offset),
            )
            messages = [dict(row) for row in cursor.fetchall()]

        return {
            "conversation": dict(conversation),
            "messages": messages,
        }

    def save_exchange(
        self,
        user_id: int,
        user_message: str,
        assistant_message: str,
        conversation_id: int | None = None,
        agent_key: str = "stockassistant",
    ) -> dict[str, Any]:
        prompt = user_message.strip()
        response = assistant_message.strip()
        resolved_agent = agent_key.strip() or "stockassistant"

        if not prompt or not response:
            raise ChatHistoryError("Los mensajes no pueden estar vacíos")
        if len(resolved_agent) > 80:
            raise ChatHistoryError("El identificador del agente es demasiado largo")

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if conversation_id is None:
                    title = " ".join(prompt.split())[:200]
                    cursor.execute(
                        """
                        INSERT INTO public.chat_conversations
                            (user_id, agent_key, title)
                        VALUES (%s, %s, %s)
                        RETURNING id, agent_key, title, created_at, updated_at
                        """,
                        (user_id, resolved_agent, title),
                    )
                    conversation = cursor.fetchone()
                    conversation_id = int(conversation["id"])
                else:
                    cursor.execute(
                        """
                        SELECT id, agent_key, title, created_at, updated_at
                        FROM public.chat_conversations
                        WHERE id = %s AND user_id = %s
                        FOR UPDATE
                        """,
                        (conversation_id, user_id),
                    )
                    conversation = cursor.fetchone()
                    if not conversation:
                        raise ChatHistoryError("Conversación no encontrada", 404)

                saved_messages: list[dict[str, Any]] = []
                for role, content in (
                    ("user", prompt),
                    ("assistant", response),
                ):
                    cursor.execute(
                        """
                        INSERT INTO public.chat_messages
                            (conversation_id, role, content)
                        VALUES (%s, %s, %s)
                        RETURNING id, role, content, created_at
                        """,
                        (conversation_id, role, content),
                    )
                    saved_messages.append(dict(cursor.fetchone()))

                cursor.execute(
                    """
                    UPDATE public.chat_conversations
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, agent_key, title, created_at, updated_at
                    """,
                    (conversation_id,),
                )
                conversation = cursor.fetchone()

            self.connection.commit()
        except ChatHistoryError:
            self.connection.rollback()
            raise
        except psycopg2.Error as exc:
            self.connection.rollback()
            raise ChatHistoryError(
                "No se pudo guardar la conversación",
                500,
            ) from exc

        return {
            "conversation": dict(conversation),
            "messages": saved_messages,
        }