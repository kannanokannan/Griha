"""
framework/sthala.py — Local inference enforcer (Sthala layer mock)

Enforces the core Sthala constraint in Griha:
- LLMs run locally via Ollama only
- No cloud fallback, ever
- Narrate/compute split enforced at call time

Part of the Griha tracer bullet: context_ops → context_boundary → sthala → coordinator
"""
import os
import logging
from typing import Optional

import litellm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local-only enforcement
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("GRIHA_MODEL", "ollama/phi3")

# Cloud model prefixes — deny if any of these appear in model name
_CLOUD_MODEL_PREFIXES = (
    "gpt-", "claude-", "gemini-", "anthropic/",
    "openai/", "azure/", "bedrock/", "vertex_ai/",
    "mistral/", "cohere/", "together_ai/",
)


def _assert_local_model(model: str) -> None:
    """
    Raise ValueError if model is not a local Ollama model.
    Fail-closed: unknown prefix = deny.
    """
    model_lower = model.lower()
    for prefix in _CLOUD_MODEL_PREFIXES:
        if model_lower.startswith(prefix):
            raise ValueError(
                f"STHALA VIOLATION: cloud model '{model}' rejected. "
                "Griha runs local inference only. Use ollama/<model_name>."
            )
    if not model_lower.startswith("ollama/"):
        raise ValueError(
            f"STHALA VIOLATION: model '{model}' not recognised as a local Ollama model. "
            "Model must start with 'ollama/'. "
            "Use ollama/phi3, ollama/llama3.2, etc."
        )


# ---------------------------------------------------------------------------
# Narrate/compute split enforcement
# ---------------------------------------------------------------------------

_ALLOWED_OPERATIONS = {"extract", "narrate"}


def _assert_allowed_operation(operation: str) -> None:
    """
    Enforce narrate/compute split.
    LLMs may only perform: extract, narrate.
    Computation must be delegated to deterministic code.
    """
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(
            f"STHALA VIOLATION: operation '{operation}' is not permitted for LLMs. "
            f"Allowed operations: {sorted(_ALLOWED_OPERATIONS)}. "
            "Computation must be delegated to deterministic code."
        )


# ---------------------------------------------------------------------------
# Local LLM call — the only entry point for LLM inference in Griha
# ---------------------------------------------------------------------------

async def local_llm_call(
    prompt: str,
    operation: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    max_tokens: int = 512,
) -> str:
    """
    Single entry point for all LLM calls in Griha.

    Enforces:
    1. Local model only (no cloud fallback)
    2. Narrate/compute split (operation must be 'extract' or 'narrate')
    3. Ollama base URL set correctly

    Args:
        prompt: User/system prompt to send.
        operation: What this call does — 'extract' or 'narrate' only.
        model: Ollama model string. Defaults to GRIHA_MODEL env var or phi3.
        system_prompt: Optional system context.
        max_tokens: Max tokens for response.

    Returns:
        Model response string.

    Raises:
        ValueError: If model is cloud-based or operation is not permitted.
        RuntimeError: If Ollama is unreachable.
    """
    resolved_model = model or DEFAULT_MODEL

    # Enforce local-only and narrate/compute split before any API call
    _assert_local_model(resolved_model)
    _assert_allowed_operation(operation)

    # Set Ollama base URL
    litellm.api_base = OLLAMA_BASE_URL

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    logger.info(f"STHALA LOCAL CALL — model={resolved_model} operation={operation} tokens={max_tokens}")

    try:
        response = await litellm.acompletion(
            model=resolved_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        result = response.choices[0].message.content
        logger.info(f"STHALA LOCAL CALL — complete, {len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"STHALA LOCAL CALL FAILED — {e}")
        raise RuntimeError(
            f"Local LLM call failed. Is Ollama running at {OLLAMA_BASE_URL}? "
            f"Error: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

async def extract(prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> str:
    """LLM intent extraction. Narrate/compute split: extraction only."""
    return await local_llm_call(prompt, operation="extract", system_prompt=system_prompt, model=model)


async def narrate(prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> str:
    """LLM narration of results. Narrate/compute split: narration only."""
    return await local_llm_call(prompt, operation="narrate", system_prompt=system_prompt, model=model)
