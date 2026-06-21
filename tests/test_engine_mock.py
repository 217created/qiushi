"""Engine mock 测试 — 验证 Engine 在 mock LLM 下可以正常运行"""
from unittest.mock import AsyncMock, patch, MagicMock


def test_process_with_result_returns_process_result():
    """process_with_result 在 mock LLM 下正常返回 ProcessResult"""
    from qiushi.engine import QiuShiEngine
    from qiushi.config import QiushiConfig, LLMConfig

    config = QiushiConfig(llm=LLMConfig(provider="test", model="test", api_key="sk-test"))

    engine = QiuShiEngine(config=config)

    # Mock _ensure_llm (创建 LLM 对象) 和 _llm.chat (返回 mock 回答)
    mock_chat = AsyncMock(return_value="这是一个测试回答。\n\\n## 总结\\n测试总结")

    with (
        patch.object(engine, "_ensure_llm", new=AsyncMock()),
        patch.object(engine, "_knowledge", new=AsyncMock()),
        patch.object(engine, "_prompt_builder", new=MagicMock()),
    ):
        # _knowledge.retrieve 需要返回知识结果
        engine._knowledge.retrieve = AsyncMock(return_value=[])
        engine._knowledge.format_context = MagicMock(return_value="")
        engine._llm = MagicMock()
        engine._llm.chat = mock_chat

        import asyncio
        result = asyncio.run(engine.process_with_result(
            session_id="test-session",
            user_input="测试问题",
            depth=2,
        ))

    assert result is not None
    assert hasattr(result, "reply")
    assert "测试" in result.reply


def test_analyzer_concept_alchemy_typo_fixed():
    """验证 matced_concepts typo 已修复为 matched_concepts"""
    from qiushi.analyzer import Analyzer

    analyzer = Analyzer()
    result = analyzer.analyze("最近压力很大")
    assert "matched_concepts" in result, f"Expected 'matched_concepts', got {list(result.keys())}"
    assert "matced_concepts" not in result, "Old typo key 'matced_concepts' should not be present"
