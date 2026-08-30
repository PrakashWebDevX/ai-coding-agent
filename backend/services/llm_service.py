"""
LLM routing service built on LiteLLM.

STRICT RULE: only free-tier Groq / OpenRouter models are permitted. No OpenAI,
Anthropic, or Gemini API keys are ever read or sent.
"""
from __future__ import annotations

import json

import litellm

from backend.config.settings import get_settings
from backend.utils.logger import get_logger

logger = get_logger("llm_service")

_ALLOWED_PREFIXES = ("groq/", "openrouter/")


def _validate_model(model: str) -> None:
    if not model.startswith(_ALLOWED_PREFIXES):
        raise ValueError(
            f"Model '{model}' is not allowed. Only Groq and OpenRouter free models are permitted."
        )


class LLMService:
    """Thin wrapper around litellm.completion with primary/fallback routing."""

    def __init__(self) -> None:
        self.settings = get_settings()
        _validate_model(self.settings.primary_model)
        _validate_model(self.settings.fallback_model)
        litellm.api_key = None  # never send a default paid-provider key

    def _api_key_for(self, model: str) -> str | None:
        if model.startswith("groq/"):
            return self.settings.groq_api_key
        if model.startswith("openrouter/"):
            return self.settings.openrouter_api_key
        return None

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """Call the primary free model, falling back to the secondary on failure."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for model in (self.settings.primary_model, self.settings.fallback_model):
            try:
                kwargs = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=self._api_key_for(model),
                )
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = await litellm.acompletion(**kwargs)
                content = response["choices"][0]["message"]["content"]
                logger.info(f"LLM call succeeded via {model}")
                return content
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LLM call failed on {model}: {exc}")
                continue

        raise RuntimeError("All configured free-tier LLM providers failed.")

    async def complete_json(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        """Call the LLM and parse strict JSON output, stripping markdown fences if present."""
        raw = await self.complete(system_prompt, user_prompt, json_mode=True, **kwargs)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse LLM JSON output: {raw}")
            raise ValueError(f"LLM did not return valid JSON: {exc}") from exc


_llm_singleton: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMService()
    return _llm_singleton
