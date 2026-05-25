"""Unified LLM client for DeepSeek, Qwen, and OpenAI via OpenAI-compatible API."""

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("model_client")


@dataclass
class Usage:
    """Token usage statistics from an LLM response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Unified response wrapper returned by every provider."""

    content: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    provider: str = ""


PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "env_key": "QWEN_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
}

PRICING_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.0005, "output": 0.002},
    "qwen-plus": {"input": 0.0008, "output": 0.002},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}

PRICING_CN: dict[str, dict[str, float]] = {
    "deepseek": {"input": 1.0, "output": 2.0},
    "qwen": {"input": 4.0, "output": 12.0},
    "openai": {"input": 150.0, "output": 600.0},
}


class CostTracker:
    """Tracks LLM API call token usage and estimates costs in CNY.

    Records every successful API call and provides cost summaries
    based on the domestic model pricing table (元/百万 tokens).
    """

    def __init__(self) -> None:
        self._records: list[tuple[Usage, str]] = []

    def record(self, usage: Usage, provider: str) -> None:
        """Record one API call's token usage.

        Args:
            usage: Token usage statistics from the LLM response.
            provider: Provider name matching a key in PRICING_CN.
        """
        self._records.append((usage, provider))
        logger.debug(
            "CostTracker record provider=%s prompt=%d completion=%d",
            provider,
            usage.prompt_tokens,
            usage.completion_tokens,
        )

    def estimated_cost(self, provider: str) -> float:
        """Return estimated total cost in CNY for the given provider.

        Args:
            provider: Provider name (deepseek / qwen / openai).

        Returns:
            Total estimated cost in yuan, rounded to 6 decimal places.
        """
        rates = PRICING_CN.get(provider, {})
        total = 0.0
        for usage, prov in self._records:
            if prov != provider:
                continue
            total += (usage.prompt_tokens / 1_000_000) * rates.get("input", 0)
            total += (usage.completion_tokens / 1_000_000) * rates.get("output", 0)
        return round(total, 6)

    def report(self, provider: str | None = None) -> None:
        """Print a human-readable cost report to the log.

        If provider is None, prints a summary for every provider that
        has recorded calls. Otherwise only prints for the given provider.

        Args:
            provider: Optional provider name to filter by.
        """
        providers = {p for _, p in self._records}
        if provider:
            providers = {provider}

        total_cost = 0.0
        for prov in sorted(providers):
            cost = self.estimated_cost(prov)
            calls = sum(1 for _, p in self._records if p == prov)
            total_cost += cost
            logger.info(
                "Cost report [%s] calls=%d cost=%.6f 元",
                prov,
                calls,
                cost,
            )

        if len(providers) > 1:
            logger.info("Cost report [total] cost=%.6f 元", total_cost)


tracker = CostTracker()


def get_provider() -> str:
    """Return the active provider name from environment."""
    return os.environ.get("LLM_PROVIDER", "deepseek").strip().lower()


def get_api_key(provider: str | None = None) -> str:
    """Read the appropriate API key from environment."""
    provider = provider or get_provider()
    cfg = PROVIDER_CONFIG.get(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}")
    key = os.environ.get(cfg["env_key"])
    if not key:
        raise ValueError(
            f"Missing environment variable {cfg['env_key']} for provider '{provider}'"
        )
    return key


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """Send a chat completion request and return the response."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier."""


class OpenAICompatibleProvider(LLMProvider):
    """Provider implementation for any OpenAI-compatible API."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._provider = provider or get_provider()
        cfg = PROVIDER_CONFIG.get(self._provider, {})
        self._api_key = api_key or get_api_key(self._provider)
        self._base_url = (base_url or cfg.get("base_url", "")).rstrip("/")
        self._model = model or cfg.get("default_model", "unknown")
        self._timeout = timeout
        self._client = httpx.Client(timeout=httpx.Timeout(timeout))

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Overrides for model, temperature, max_tokens, etc.

        Returns:
            LLMResponse containing the assistant reply and usage stats.

        Raises:
            httpx.HTTPStatusError: On non-2xx API responses.
            httpx.RequestError: On connection / timeout errors.
        """
        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self._model),
            "messages": messages,
            **kwargs,
        }
        logger.debug(
            "Sending request to %s model=%s", self._provider, payload["model"]
        )

        resp = self._client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        content: str = choice["message"]["content"] or ""
        raw_usage = data.get("usage", {})
        usage = Usage(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )
        logger.info(
            "Received response provider=%s model=%s tokens=%d",
            self._provider,
            data.get("model", payload["model"]),
            usage.total_tokens,
        )
        tracker.record(usage, self._provider)
        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model", payload["model"]),
            provider=self._provider,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()


def create_provider(
    provider: str | None = None,
    model: str | None = None,
) -> OpenAICompatibleProvider:
    """Factory that creates an OpenAICompatibleProvider from environment config.

    Args:
        provider: Provider name (deepseek/qwen/openai). Defaults to LLM_PROVIDER env.
        model: Model name override. Defaults to the provider's default model.

    Returns:
        Configured OpenAICompatibleProvider instance.
    """
    return OpenAICompatibleProvider(provider=provider, model=model)


def estimate_tokens(text: str) -> int:
    """Roughly estimate token count (Chinese ~1.5 chars/token, English ~4 chars/token)."""
    chinese_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_count = len(text) - chinese_count
    return round(chinese_count / 1.5 + other_count / 4)


def calculate_cost(
    usage: Usage,
    model: str = "",
    pricing_map: dict[str, dict[str, float]] | None = None,
) -> float:
    """Calculate request cost in USD based on token usage.

    Args:
        usage: Token usage statistics.
        model: Model name used for pricing lookup.
        pricing_map: Optional custom pricing override.

    Returns:
        Cost in USD.
    """
    pmap = pricing_map or PRICING_PER_1K_TOKENS
    rates = pmap.get(model, {})
    input_cost = (usage.prompt_tokens / 1000) * rates.get("input", 0)
    output_cost = (usage.completion_tokens / 1000) * rates.get("output", 0)
    return round(input_cost + output_cost, 6)


def chat_with_retry(
    messages: list[dict[str, str]],
    provider: LLMProvider | None = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> LLMResponse:
    """Send a chat request with automatic retry on transient failures.

    Args:
        messages: Chat messages.
        provider: An LLMProvider instance. Created from env if None.
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Initial delay in seconds before the first retry.
        **kwargs: Passed through to provider.chat().

    Returns:
        LLMResponse on success.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    prov = provider or OpenAICompatibleProvider()
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return prov.chat(messages, **kwargs)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            status = ""
            if isinstance(exc, httpx.HTTPStatusError):
                status = f" HTTP {exc.response.status_code}"
            logger.warning(
                "Attempt %d/%d failed%s: %s",
                attempt,
                max_retries,
                status,
                exc,
            )
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.info("Retrying in %.1fs...", delay)
                time.sleep(delay)

    raise RuntimeError(
        f"All {max_retries} retries exhausted for provider={prov.provider_name}"
    ) from last_exc


def quick_chat(
    prompt: str,
    system_prompt: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """One-shot chat: build messages and call the LLM.

    Args:
        prompt: The user message.
        system_prompt: Optional system instruction.
        provider: Provider name override (default from LLM_PROVIDER env).
        model: Model name override.
        **kwargs: Additional arguments for chat_with_retry.

    Returns:
        LLMResponse from the model.
    """
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    prov = OpenAICompatibleProvider(provider=provider, model=model)
    return chat_with_retry(messages, provider=prov, **kwargs)


if __name__ == "__main__":
    import sys

    test_prompt = "Hello! Say hi in one sentence."
    if len(sys.argv) > 1:
        test_prompt = " ".join(sys.argv[1:])

    print(f"PROMPT: {test_prompt}")
    print(f"PROVIDER: {get_provider()}")
    print("-" * 50)

    try:
        resp = quick_chat(test_prompt)
        print(f"MODEL: {resp.model}")
        print(f"CONTENT: {resp.content}")
        print(f"USAGE: {resp.usage}")
        cost = calculate_cost(resp.usage, resp.model)
        print(f"COST: ${cost:.6f}")

        print()
        print("--- Token estimation ---")
        estimated = estimate_tokens(test_prompt + resp.content)
        print(f"Estimated tokens: {estimated}")
    except Exception as exc:
        logger.exception("Test run failed")
        print(f"ERROR: {exc}")
