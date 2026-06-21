"""LLM 客户端测试（mock httpx，不发起真实调用）"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from qiushi.config import QiushiConfig, LLMConfig
from qiushi.llm import create_llm, _DeepSeekClient, _OllamaClient, _LiteLLMClient


def test_create_deepseek():
    """创建 DeepSeek 客户端（litellm 已安装时返回 LiteLLMClient）"""
    config = QiushiConfig(llm=LLMConfig(provider="deepseek", api_key="sk-test"))
    client = create_llm(config)
    # litellm 已安装时返回的是 LiteLLMClient，确保不是 None
    assert client is not None


def test_create_ollama():
    """创建 Ollama 客户端"""
    config = QiushiConfig(llm=LLMConfig(provider="ollama", model="qwen3:8b"))
    client = create_llm(config)
    assert client is not None


@pytest.mark.asyncio
async def test_deepseek_chat():
    """DeepSeek chat 能解包 mock 响应"""
    config = QiushiConfig(llm=LLMConfig(provider="deepseek", api_key="sk-test"))
    client = _DeepSeekClient(config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "你好"}}]}

    client._client = AsyncMock()
    client._client.post = AsyncMock(return_value=mock_response)

    result = await client.chat([{"role": "user", "content": "你好"}])
    assert result == "你好"

    await client.close()


@pytest.mark.asyncio
async def test_deepseek_chat_failure():
    """DeepSeek 调用失败时正常抛异常"""
    config = QiushiConfig(llm=LLMConfig(provider="deepseek", api_key="sk-test"))
    client = _DeepSeekClient(config)

    from httpx import HTTPStatusError, Request
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=mock_resp
    )

    client._client = AsyncMock()
    client._client.post = AsyncMock(return_value=mock_resp)

    from qiushi.llm import LLMError
    with pytest.raises(LLMError):
        await client.chat([{"role": "user", "content": "你好"}])

    await client.close()


@pytest.mark.asyncio
async def test_ollama_chat():
    """Ollama 客户端 mock 通信"""
    client = _OllamaClient(base_url="http://localhost:11434")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"content": "你好"}}

    client._client = AsyncMock()
    client._client.post = AsyncMock(return_value=mock_response)

    result = await client.chat([{"role": "user", "content": "你好"}], system="你是一个助手")
    assert result == "你好"

    await client.close()
