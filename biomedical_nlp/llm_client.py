from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class LLMResult:
    content: str
    reasoning: Optional[str] = None
    raw: Optional[Any] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_reasoning(raw) -> Optional[str]:
    """Pull chain-of-thought text out of a LangChain AIMessage where available."""
    # DeepSeek-reasoner / OpenAI o-series
    reasoning = raw.additional_kwargs.get("reasoning_content")
    if reasoning:
        return reasoning
    # Anthropic extended thinking
    for block in raw.additional_kwargs.get("thinking_blocks", []):
        if block.get("type") == "thinking":
            return block.get("thinking")
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_llm_response(
    llm: BaseChatModel,
    user_prompt: str,
    *,
    system_prompt: str = "",
    max_retries: int = 5,
    logger: Optional[logging.Logger] = None,
) -> LLMResult:
    """Call an LLM with exponential-backoff retry and return a structured result.

    Parameters
    ----------
    llm:
        Any instantiated LangChain chat model (e.g. ``ChatOpenAI``).
        Temperature, max_tokens, and other generation params are set on
        the model object itself, not passed here.
    user_prompt:
        The user-turn message.
    system_prompt:
        Optional system / developer prompt.
    max_retries:
        Maximum number of attempts before raising (default 5).
    logger:
        Optional logger for per-attempt warnings and retry notices.
    """
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=user_prompt))

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            raw = llm.invoke(messages)
            return LLMResult(
                content=raw.content,
                reasoning=_extract_reasoning(raw),
                raw=raw,
            )
        except Exception as e:
            last_error = e
            if logger:
                logger.warning("LLM call failed on attempt %d: %s", attempt + 1, e)
            if attempt < max_retries - 1:
                wait = 5 * (2 ** attempt)
                if logger:
                    logger.info("Retrying after %d seconds...", wait)
                time.sleep(wait)

    assert last_error is not None
    raise last_error


def clean_json_response(response: str) -> str:
    """Strip markdown code fences from an LLM JSON response.

    Handles three cases:
    - Complete fence:  ```json { ... } ```
    - Unclosed fence:  ```json { ...
    - Raw JSON:        { ... }
    """
    match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    json_start = response.find("```json")
    if json_start != -1:
        return response[json_start + 7:].strip()
    return response


__all__ = [
    "LLMResult",
    "get_llm_response",
    "clean_json_response",
]
