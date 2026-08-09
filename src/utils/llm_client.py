"""Unified LLM client with multi-provider routing and automatic fallback.

All LLM calls in the system go through this client. No agent calls any
provider API directly. See ARCHITECTURE.md Section 7 and CONVENTIONS.md
Section 4.

Provider routing:
    task name → MODEL_FOR_TASK lookup → primary provider
    if 429 → retry with exponential backoff (up to 3 attempts)
    if still failing → fall back to OpenRouter

All four providers (Gemini, Groq, Cerebras, OpenRouter) expose
OpenAI-compatible chat/completions endpoints, so we use a single
OpenAI SDK client per provider with different base URLs.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TypeVar, Type

from openai import APIConnectionError, OpenAI, RateLimitError
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.models import (
    FALLBACK_PROVIDER,
    MODEL_FOR_TASK,
    OPENROUTER_DEFAULT_MODEL,
    OPENROUTER_MODEL_MAP,
    PROVIDER_BASE_URLS,
)
from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """Response from an LLM call, including metadata for token tracking."""

    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int

    def parse_json(self) -> dict:
        """Parse the response content as JSON.

        Raises:
            ValueError: If the content is not valid JSON.
        """
        content = self.content.strip()
        
        # Robust regex to extract JSON if wrapped in markdown or conversational filler
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            content = match.group(1)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM response is not valid JSON: {e}\nContent: {self.content[:500]}"
            ) from e

    T = TypeVar("T", bound=BaseModel)

    def parse_pydantic(self, model_class: Type[T]) -> T:
        """Extract JSON and parse it into a Pydantic model."""
        raw_dict = self.parse_json()
        return model_class.model_validate(raw_dict)


class LLMClient:
    """Multi-provider LLM client with routing, retry, and fallback.

    Usage:
        client = LLMClient()
        response = client.complete(
            task="relevance_filter",
            messages=[
                {"role": "system", "content": "You are a relevance filter..."},
                {"role": "user", "content": "[SRC_01] Some competitor snippet..."},
            ],
            json_mode=True,
        )
        result = response.parse_json()
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._clients: dict[str, OpenAI] = {}
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize an OpenAI client for each provider that has an API key."""
        key_map = {
            "gemini": self._settings.gemini_api_key,
            "groq": self._settings.groq_api_key,
            "cerebras": self._settings.cerebras_api_key,
            "openrouter": self._settings.openrouter_api_key,
        }
        for provider, api_key in key_map.items():
            if api_key:
                self._clients[provider] = OpenAI(
                    api_key=api_key,
                    base_url=PROVIDER_BASE_URLS[provider],
                )
            else:
                logger.warning(
                    "No API key for provider '%s' — it will be unavailable.", provider
                )

    def complete(
        self,
        task: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
        response_model: Type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Send a completion request, routed to the appropriate provider.

        Args:
            task: Task name from MODEL_FOR_TASK (e.g. "relevance_filter").
            messages: Chat messages in OpenAI format.
            temperature: Sampling temperature (0.0 = deterministic).
            json_mode: If True, request JSON output format from the model.

        Returns:
            LLMResponse with content and usage metadata.

        Raises:
            KeyError: If task is not in MODEL_FOR_TASK.
            RuntimeError: If both primary and fallback providers fail.
        """
        if task not in MODEL_FOR_TASK:
            raise KeyError(
                f"Unknown task '{task}'. Valid tasks: {list(MODEL_FOR_TASK.keys())}"
            )

        config = MODEL_FOR_TASK[task]
        primary_provider = config.provider
        model = config.model

        if response_model:
            schema = response_model.model_json_schema()
            schema_prompt = (
                f"\n\nCRITICAL INSTRUCTION: You MUST return your answer as a valid JSON object. "
                f"Your JSON object MUST exactly match the following JSON Schema structure.\n"
                f"DO NOT return the JSON Schema itself. Return the DATA that matches the schema.\n"
                f"{json.dumps(schema, indent=2)}"
            )
            # Append schema instructions to the last message (typically user)
            messages = list(messages)
            messages[-1] = {**messages[-1], "content": messages[-1]["content"] + schema_prompt}
            json_mode = True

        # Try primary provider with retry on rate limits
        primary_error = None
        try:
            return self._call_with_retry(
                provider=primary_provider,
                model=model,
                messages=messages,
                temperature=temperature,
                json_mode=json_mode,
            )
        except Exception as e:
            primary_error = e
            logger.warning(
                "Primary provider '%s' failed for task '%s': %s. "
                "Falling back to '%s'.",
                primary_provider,
                task,
                e,
                FALLBACK_PROVIDER,
            )

        # Fallback to OpenRouter
        if FALLBACK_PROVIDER not in self._clients:
            raise RuntimeError(
                f"Primary provider '{primary_provider}' failed and fallback "
                f"provider '{FALLBACK_PROVIDER}' has no API key configured."
            ) from primary_error

        try:
            # OpenRouter uses provider-prefixed model IDs
            fallback_model = model
            if FALLBACK_PROVIDER == "openrouter":
                fallback_model = OPENROUTER_MODEL_MAP.get(model, OPENROUTER_DEFAULT_MODEL)

            return self._call_with_retry(
                provider=FALLBACK_PROVIDER,
                model=fallback_model,
                messages=messages,
                temperature=temperature,
                json_mode=json_mode,
            )
        except Exception as fallback_error:
            raise RuntimeError(
                f"Both primary ('{primary_provider}') and fallback "
                f"('{FALLBACK_PROVIDER}') providers failed for task '{task}'."
            ) from fallback_error

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_with_retry(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        json_mode: bool,
    ) -> LLMResponse:
        """Make an LLM call with automatic retry on rate limits and connection errors."""
        if provider not in self._clients:
            raise RuntimeError(
                f"Provider '{provider}' is not available (missing API key)."
            )

        client = self._clients[provider]

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        logger.debug(
            "LLM call: provider=%s model=%s messages=%d json_mode=%s",
            provider,
            model,
            len(messages),
            json_mode,
        )

        response = client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        logger.info(
            "LLM response: provider=%s model=%s in_tokens=%d out_tokens=%d",
            provider,
            model,
            input_tokens,
            output_tokens,
        )

        return LLMResponse(
            content=content,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
