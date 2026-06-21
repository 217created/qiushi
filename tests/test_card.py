"""思辨卡片测试"""

from qiushi.card import generate_card, _generate_reflection, _append_to_library


def test_generate_card_no_keyword():
    """无关键词生成卡片不报错"""
    result = generate_card()
    assert "思辨卡片" in result
    assert result.startswith("┌")


def test_generate_card_with_keyword():
    """有关键词时返回卡片"""
    result = generate_card("矛盾")
    assert "思辨卡片" in result
    assert len(result) > 50


def test_generate_card_garbage_keyword():
    """无意义关键词返回兜底内容"""
    result = generate_card("xyzxyzxyz123")
    # 要么返回卡片，要么返回 "没有找到相关内容"
    assert result is not None


def test_generate_reflection():
    """反问句格式正确"""
    question = _generate_reflection("实践论", "学习")
    assert isinstance(question, str)
    assert len(question) > 5
    assert question.endswith("？")


def test_append_to_library(tmp_path, monkeypatch):
    """追加卡片到本地文件"""
    from pathlib import Path
    monkeypatch.setattr("qiushi.card.Path.home", lambda: tmp_path)

    _append_to_library("实践论", "实践是检验真理的唯一标准")
    card_path = tmp_path / ".qiushi" / "cards.md"
    assert card_path.exists()
    content = card_path.read_text(encoding="utf-8")
    assert "实践论" in content
