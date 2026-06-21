"""引擎核心路径测试"""

import pytest
from qiushi.engine import QiuShiEngine, ProcessResult
from qiushi.analyzer import Analyzer, parse_sections
from qiushi.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_engine_initialize():
    engine = QiuShiEngine()
    assert engine is not None
    await engine.close()


@pytest.mark.asyncio
async def test_engine_context_manager():
    async with QiuShiEngine() as engine:
        assert engine is not None


def test_system_prompt_loaded():
    pb = PromptBuilder()
    prompt = pb.get_system_prompt()
    assert len(prompt) > 50
    assert "求是" in prompt


@pytest.mark.asyncio
async def test_sanitize_removes_prohibited():
    async with QiuShiEngine() as engine:
        result = engine._sanitize("你很有天赋")
        assert "（就事论事）" in result


def test_sections_parsing():
    result = parse_sections("【分析】这是分析内容。\n【反思】这是反驳内容。\n【总结】这是总结内容。")
    assert "分析" in result["main"]
    assert "反驳" in result["rebuttal"]
    assert "总结" in result["summary"]


def test_concept_alchemy_match():
    analyzer = Analyzer()
    result = analyzer.analyze("最近压力很大")
    assert "压力" in result["matched_concepts"]


def test_macro_trigger_match():
    analyzer = Analyzer()
    result = analyzer.analyze("30岁转行来得及吗")
    assert result["matched_macro"] in ("30岁", "转行")


def test_contradiction_detection():
    analyzer = Analyzer()
    r1 = analyzer.analyze("该不该辞职做独立开发")
    assert "职业选择" in r1["matched_contradictions"]

    r2 = analyzer.analyze("和女朋友吵架了")
    assert "感情关系" in r2["matched_contradictions"]

    r3 = analyzer.analyze("今天天气不错")
    assert len(r3["matched_contradictions"]) == 0


def test_public_format_excludes_rebuttal():
    result = ProcessResult(
        reply="【分析】分析内容\n【反思】反驳内容\n【总结】总结内容",
        sections={"main": "分析内容", "rebuttal": "反驳内容", "summary": "总结内容"},
        knowledge_results=[], matched_concepts=[], matched_macro=None,
        matched_contradictions=[], metaphors_used=[], depth=2, auto_saved=False,
    )
    public = result.public_text
    assert "分析内容" in public
    assert "总结内容" in public
    assert "反驳内容" not in public


def test_explain_shows_auto_saved():
    result = ProcessResult(
        reply="【分析】分析\n【反思】反思\n【总结】总结",
        sections={"main": "分析", "rebuttal": "反思", "summary": "总结"},
        knowledge_results=[], matched_concepts=[], matched_macro=None,
        matched_contradictions=["职业选择"], metaphors_used=[], depth=2, auto_saved=True,
    )
    text = result.to_explain_text("测试")
    assert "已自动记录" in text
    assert "矛盾类型" in text
