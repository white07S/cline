"""OpenAI chat client wrapper.

Why a wrapper:
  - Centralize retry / timeout policy
  - Wrap openai exceptions in domain errors (LLMError hierarchy)
  - Make the API the same shape regardless of OpenAI vs Azure OpenAI later
  - All inputs/outputs are Pydantic — no dict[str, Any] anywhere
"""

from __future__ import annotations

from typing import Literal, cast

from openai import APIError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from app.logging import get_logger
from app.settings import get_settings

log = get_logger(__name__)


# ── Domain models ───────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


# ── Errors ──────────────────────────────────────────────────────


class LLMError(Exception):
    """Base for all LLM-related failures."""


class LLMRateLimitError(LLMError):
    pass


class LLMAPIError(LLMError):
    pass


# ── Client ──────────────────────────────────────────────────────


def _build_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.openai.api_key.get_secret_value(),
        timeout=settings.openai.default_timeout_seconds,
    )


async def chat(request: ChatRequest) -> ChatResponse:
    """Synchronous (non-streaming) chat completion. Streaming version: chat_stream."""
    settings = get_settings()
    client = _build_client()

    # Cast through ChatCompletionMessageParam: openai's TypedDict requires the
    # exact discriminated-union shape, but ChatMessage is a 1:1 structural
    # match (role + content) so the cast is sound.
    messages = cast(
        list[ChatCompletionMessageParam],
        [m.model_dump() for m in request.messages],
    )

    try:
        completion = await client.chat.completions.create(
            model=settings.openai.chat_model,
            messages=messages,
            temperature=request.temperature or settings.openai.default_temperature,
            max_tokens=request.max_tokens or settings.openai.default_max_tokens,
            stream=False,
        )
    except RateLimitError as e:
        log.warning("openai_rate_limited", error=str(e))
        raise LLMRateLimitError("OpenAI rate limit exceeded") from e
    except APIError as e:
        log.exception("openai_api_error")
        raise LLMAPIError(f"OpenAI API error: {e}") from e

    choice = completion.choices[0]
    usage = completion.usage
    if choice.message.content is None:
        raise LLMAPIError("OpenAI returned an empty completion")
    if usage is None:
        raise LLMAPIError("OpenAI returned no usage information")

    return ChatResponse(
        content=choice.message.content,
        model=completion.model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )
