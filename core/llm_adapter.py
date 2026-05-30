"""
LLMAdapter — single interface for all LLM providers.
Swap Anthropic ↔ OpenAI ↔ Ollama by changing profile.yaml.
Framework code never imports litellm directly — always through here.
"""
import logging
from typing import Optional
import litellm

logger = logging.getLogger(__name__)

OLLAMA_ENV_DEFAULTS = {
    "OLLAMA_MAX_LOADED_MODELS": "1",
    "OLLAMA_KEEP_ALIVE":        "0",
}

# Apply Ollama runtime defaults — setdefault respects env vars already set
import os as _os
for _k, _v in OLLAMA_ENV_DEFAULTS.items():
    _os.environ.setdefault(_k, _v)


class LLMAdapter:

    def __init__(self, model: str = "ollama/phi3", base_url: Optional[str] = "http://localhost:11434", max_tokens: int = 512, temperature: float = 0.1):
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        if base_url:
            litellm.api_base = base_url

    async def complete(self, messages: list, system: Optional[str] = None, json_mode: bool = False, max_tokens: Optional[int] = None) -> str:
        if system:
            messages = [{"role": "system", "content": system}] + messages
        kwargs = {"model": self.model, "messages": messages, "max_tokens": max_tokens or self.max_tokens, "temperature": self.temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await litellm.acompletion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed [{self.model}]: {e}")
            raise

    async def extract_json(self, messages: list, system: str) -> dict:
        import json
        raw = await self.complete(messages, system=system, json_mode=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM extraction failed — invalid JSON: {e}")

    @classmethod
    def from_profile(cls, profile: dict) -> "LLMAdapter":
        return cls(model=profile.get("model", "ollama/phi3"), base_url=profile.get("base_url", "http://localhost:11434"), max_tokens=profile.get("max_tokens", 512), temperature=profile.get("temperature", 0.1))

    @classmethod
    def cloud(cls, model: str = "claude-sonnet-4-20250514") -> "LLMAdapter":
        return cls(model=model, base_url=None)
