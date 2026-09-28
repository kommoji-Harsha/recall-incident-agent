"""
backend/app/llm/client.py — Groq LLM client wrapper with exponential backoff retry,
model fallback, JSON validation, and graceful degradation.
"""

import asyncio
import json
import logging
import os
import random
from typing import Type, TypeVar
from groq import Groq
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """LLM client wrapping official Groq SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        primary_model: str = "openai/gpt-oss-120b",
        fallback_model: str = "qwen/qwen3-32b",
        max_retries_per_model: int = 3,
        base_backoff_seconds: float = 0.5,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.primary_model = primary_model or os.environ.get("GROQ_PRIMARY_MODEL", "openai/gpt-oss-120b")
        self.fallback_model = fallback_model or os.environ.get("GROQ_FALLBACK_MODEL", "qwen/qwen3-32b")
        self.max_retries_per_model = max_retries_per_model
        self.base_backoff_seconds = base_backoff_seconds
        self._groq_client: Groq | None = None

    @property
    def groq(self) -> Groq:
        if self._groq_client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not configured.")
            self._groq_client = Groq(api_key=self.api_key)
        return self._groq_client

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> tuple[T | None, str, list[str]]:
        warnings: list[str] = []
        models_to_try = [self.primary_model, self.fallback_model]

        for model in models_to_try:
            for attempt in range(1, self.max_retries_per_model + 1):
                try:
                    response_text = await asyncio.to_thread(
                        self._call_groq,
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=prompt,
                    )

                    clean_text = self._clean_json_text(response_text)
                    raw_json = json.loads(clean_text)
                    parsed_obj = response_schema.model_validate(raw_json)
                    return parsed_obj, model, warnings

                except Exception as ex:
                    warn_msg = f"Model {model} attempt {attempt}/{self.max_retries_per_model} failed: {ex}"
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)

                    if attempt < self.max_retries_per_model:
                        backoff = (self.base_backoff_seconds * (2 ** (attempt - 1))) + random.uniform(0.05, 0.25)
                        await asyncio.sleep(backoff)

            warnings.append(
                f"Model {model} failed all {self.max_retries_per_model} retries. Switching model if available."
            )

        warnings.append("All LLM attempts failed across primary and fallback models. Returning degraded response.")
        return None, "none", warnings

    def _call_groq(self, model: str, system_prompt: str, user_prompt: str) -> str:
        completion = self.groq.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content or ""

    @staticmethod
    def _clean_json_text(text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
