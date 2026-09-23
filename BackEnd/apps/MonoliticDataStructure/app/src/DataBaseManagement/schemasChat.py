from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    conversation_id: int | None = Field(default=None, ge=1)
    provider: Literal["openai", "ollama"] = "openai"
    agent_key: str = Field(
        default="stockassistant",
        min_length=1,
        max_length=80,
    )