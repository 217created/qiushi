"""知识库写操作测试 — 通过 SQLite"""

import pytest
from qiushi.writer import write_note
from qiushi.db import (
    init_db, add_entry, upsert_contradiction, upsert_decision,
    mark_decision_done, list_entries, get_user_contradictions,
    get_user_decisions,
)


def test_write_note():
    eid = write_note("今天想通了，先不辞职", tags=["职业"])
    entries = list_entries("note")
    assert len(entries) > 0


def test_upsert_contradiction():
    upsert_contradiction("user-1", "职业选择", "该不该辞职")
    records = get_user_contradictions("user-1")
    assert len(records) == 1
    assert records[0]["type"] == "职业选择"


def test_upsert_contradiction_increments_count():
    upsert_contradiction("user-2", "感情关系", "吵架了")
    upsert_contradiction("user-2", "感情关系", "又吵架了")
    records = get_user_contradictions("user-2")
    assert len(records) == 1
    assert records[0]["count"] >= 2


def test_upsert_decision():
    upsert_decision("user-1", "业余验证MVP", "职业选择")
    decisions = get_user_decisions("user-1")
    assert len(decisions) >= 1


def test_mark_done():
    upsert_decision("user-3", "先学习再跳槽")
    result = mark_decision_done("user-3", "先学习再跳槽")
    assert result is True
    decisions = get_user_decisions("user-3")
    assert decisions[0]["executed"] == 1


def test_mark_done_not_found():
    result = mark_decision_done("user-x", "不存在的建议")
    assert result is False


def test_list_entries():
    write_note("测试笔记", tags=["test"])
    upsert_contradiction("user-list", "测试矛盾", "A vs B")
    entries = list_entries()
    # 应该包含 note 和可能的其他类型
    assert len(entries) > 0
