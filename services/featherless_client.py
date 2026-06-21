"""
Featherless AI client – wraps the OpenAI-compatible API endpoint.
Provides sync and async methods used by all agents.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")

# Model pool used for consensus
CONSENSUS_MODELS = [
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    "Qwen/Qwen3-8B",
    "meta-llama/Llama-3.3-70B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]

DEFAULT_MODEL = "Qwen/Qwen3-8B"
VISION_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"


class FeatherlessClient:
    """Async client for Featherless AI API (OpenAI-compatible)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or FEATHERLESS_API_KEY
        self.base_url = base_url or FEATHERLESS_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat completion request and return the assistant message."""
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        logger.debug("Featherless response (model=%s): %s...", model, content[:120])
        return content

    async def vision_completion(
        self,
        prompt: str,
        image_base64: str,
        media_type: str = "image/png",
        model: str = VISION_MODEL,
    ) -> str:
        """Send a vision completion request with an image."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_base64}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        return await self.chat_completion(messages, model=model, temperature=0.1)

    async def json_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Request JSON-structured output and parse the result."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = await self.chat_completion(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=4096,
        )
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)

    async def consensus_completions(
        self,
        system_prompt: str,
        user_prompt: str,
        models: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run the same prompt against multiple models in parallel
        and return their responses for consensus aggregation.
        """
        import asyncio

        models = models or CONSENSUS_MODELS
        tasks = [
            self.json_completion(system_prompt, user_prompt, model=m)
            for m in models
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for model, result in zip(models, results):
            if isinstance(result, Exception):
                logger.warning("Consensus model %s failed: %s", model, result)
                output.append({"model": model, "error": str(result), "response": None})
            else:
                output.append({"model": model, "response": result, "error": None})
        return output


# Shared singleton
featherless = FeatherlessClient()
