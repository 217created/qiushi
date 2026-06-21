"""风格处理测试"""

import pytest
from qiushi.style import StyleProcessor


@pytest.fixture
def style() -> StyleProcessor:
    return StyleProcessor()


def test_loads_metaphors(style: StyleProcessor):
    assert len(style._metaphors) > 30


def test_loads_prohibited(style: StyleProcessor):
    assert len(style._prohibited) > 10
    assert "你很棒" in style._prohibited


def test_filter_prohibited(style: StyleProcessor):
    text = "你很有天赋，这是一个好问题"
    result = style.filter_prohibited(text)
    assert "（就事论事）" in result
    assert "你很有天赋" not in result


def test_filter_metaphors_by_scenario(style: StyleProcessor):
    general = style.filter_metaphors_by_scenario("general")
    relationship = style.filter_metaphors_by_scenario("relationship")
    assert len(general) > len(relationship)
    assert all("relationship" in m.get("scenario", []) for m in relationship)


def test_build_style_prompt_match(style: StyleProcessor):
    prompt, used = style.build_style_prompt("最近压力很大", "general")
    assert len(prompt) > 0
    assert len(used) > 0


def test_build_style_prompt_no_match(style: StyleProcessor):
    prompt, used = style.build_style_prompt("今天天气不错", "general")
    assert prompt == ""
    assert used == []


def test_build_style_prompt_relationship(style: StyleProcessor):
    prompt, used = style.build_style_prompt("和女朋友吵架了", "relationship")
    assert len(prompt) > 0  # 感情类场景应有匹配
    assert len(used) > 0


def test_sanitize_removes_markdown_headers(style: StyleProcessor):
    text = "# 标题\n\n正文内容"
    result = style.sanitize(text)
    assert "标题" not in result
    assert "正文内容" in result


def test_sanitize_collapses_lists(style: StyleProcessor):
    text = "1. 第一点\n2. 第二点\n3. 第三点"
    result = style.sanitize(text)
    assert "第一点" in result
    assert "；" in result  # 列表被合并
