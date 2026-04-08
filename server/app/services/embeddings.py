"""OpenAI embeddings wrapper. Pydantic in/out — no dicts."""

from __future__ import annotations

import asyncio

from openai import APIError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, Field

from app.logging import get_logger
from app.services.llm import LLMAPIError, LLMRateLimitError
from app.settings import get_settings

log = get_logger(__name__)


class Embedding(BaseModel):
    text: str
    vector: list[float] = Field(min_length=1)
    model: str
    dim: int


def _build_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.openai.api_key.get_secret_value(),
        timeout=settings.openai.default_timeout_seconds,
    )


async def embed_one(text: str) -> Embedding:
    settings = get_settings()
    client = _build_client()

    try:
        response = await client.embeddings.create(
            model=settings.openai.embedding_model,
            input=text,
        )
    except RateLimitError as e:
        log.warning("openai_embed_rate_limited")
        raise LLMRateLimitError("OpenAI rate limit exceeded") from e
    except APIError as e:
        log.exception("openai_embed_error")
        raise LLMAPIError(f"OpenAI API error: {e}") from e

    item = response.data[0]
    return Embedding(
        text=text,
        vector=item.embedding,
        model=response.model,
        dim=len(item.embedding),
    )


async def embed_many(texts: list[str]) -> list[Embedding]:
    """Bounded-concurrency batch embedding.

    We use a semaphore rather than unbounded asyncio.gather because:
      1. OpenAI enforces per-minute token / request limits
      2. The async event loop will happily fan out 10,000 requests at once
    """
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.openai.max_concurrent_calls)

    async def _one(text: str) -> Embedding:
        async with semaphore:
            return await embed_one(text)

    return await asyncio.gather(*[_one(t) for t in texts])
