"""LLM 客户端 — LiteLLM 统一接口 + 轻量降级"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator

import httpx

from .config import QiushiConfig


class LLMError(Exception):
    """LLM 调用失败的统一异常"""


class LLMClient(ABC):
    """LLM 抽象接口"""

    @abstractmethod
    async def chat(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> str: ...

    async def chat_stream(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """流式接口：默认按块返回完整文本（子类可覆写为真正的SSE流）"""
        yield await self.chat(messages, system=system, temperature=temperature)

    async def close(self):
        """释放资源（子类可覆写）"""


def create_llm(config: QiushiConfig) -> LLMClient:
    provider = config.llm.provider
    try:
        import litellm  # noqa: F401
        return _LiteLLMClient(config)
    except ImportError:
        pass
    if provider == "deepseek":
        return _DeepSeekClient(config)
    if provider == "ollama":
        return _OllamaClient()
    raise LLMError(
        f"不支持的内置 provider: {provider}。请安装 litellm: pip install 'qiushi[all]'"
    )


# ── LiteLLM 实现 ─────────────────────────────────────────────────

class _LiteLLMClient(LLMClient):
    def __init__(self, config: QiushiConfig):
        import litellm
        self._litellm = litellm
        self._config = config
        api_key = config.get_effective_api_key()
        if api_key:
            provider = config.llm.provider
            import os
            os.environ.setdefault(f"{provider.upper()}_API_KEY", api_key)
        if config.llm.base_url:
            provider = config.llm.provider
            import os
            os.environ.setdefault(f"{provider.upper()}_API_BASE", config.llm.base_url)

    async def chat(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> str:
        msgs = list(messages)
        if system:
            msgs.insert(0, {"role": "system", "content": system})
        config = self._config
        model_str = f"{config.llm.provider}/{config.llm.model}"
        try:
            resp = await self._litellm.acompletion(
                model=model_str, messages=msgs, temperature=temperature, timeout=config.llm.timeout,
            )
            return resp.choices[0].message.content
        except Exception as e:
            raise LLMError(f"LLM 调用失败 ({config.llm.provider}/{config.llm.model}): {e}") from e

    async def chat_stream(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        msgs = list(messages)
        if system:
            msgs.insert(0, {"role": "system", "content": system})
        config = self._config
        model_str = f"{config.llm.provider}/{config.llm.model}"
        try:
            stream = await self._litellm.acompletion(
                model=model_str, messages=msgs, temperature=temperature,
                timeout=config.llm.timeout, stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise LLMError(f"LLM 流式调用失败 ({config.llm.provider}/{config.llm.model}): {e}") from e


# ── 原生 DeepSeek 降级 ───────────────────────────────────────────

class _DeepSeekClient(LLMClient):
    def __init__(self, config: QiushiConfig):
        import httpx
        api_key = config.get_effective_api_key()
        base_url = config.llm.base_url or "https://api.deepseek.com/v1"
        self._model = config.llm.model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=config.llm.timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def chat(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> str:
        msgs = list(messages)
        if system:
            msgs.insert(0, {"role": "system", "content": system})
        resp = await self._client.post(
            "/chat/completions",
            json={"model": self._model, "messages": msgs, "temperature": temperature, "stream": False},
        )
        try:
            resp.raise_for_status()
        except Exception as e:
            raise LLMError(f"DeepSeek 调用失败: {e}") from e
        return resp.json()["choices"][0]["message"]["content"]

    async def chat_stream(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        msgs = list(messages)
        if system:
            msgs.insert(0, {"role": "system", "content": system})
        async with httpx.AsyncClient(
            base_url=self._client.base_url,
            timeout=self._client.timeout,
            headers=self._client.headers,
        ) as client:
            async with client.stream(
                "POST", "/chat/completions",
                json={"model": self._model, "messages": msgs, "temperature": temperature, "stream": True},
            ) as resp:
                try:
                    resp.raise_for_status()
                except Exception as e:
                    raise LLMError(f"DeepSeek 流式调用失败: {e}") from e
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue

    async def close(self):
        await self._client.aclose()


# ── 原生 Ollama 降级 ─────────────────────────────────────────────

class _OllamaClient(LLMClient):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:8b"):
        import httpx
        self._model = model
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=120)

    async def chat(
        self, messages: list[dict], system: str | None = None, temperature: float = 0.7
    ) -> str:
        payload = {"model": self._model, "messages": messages, "temperature": temperature, "stream": False}
        if system:
            payload["system"] = system
        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            raise LLMError(f"Ollama 调用失败: {e}") from e

    async def close(self):
        await self._client.aclose()
