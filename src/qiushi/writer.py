"""知识库写操作 — 通过 SQLite"""

from __future__ import annotations

from .db import (
    add_entry,
    upsert_contradiction as db_upsert_contradiction,
    upsert_decision as db_upsert_decision,
    mark_decision_done,
    get_user_decisions,
    list_entries as db_list_entries,
)


def write_note(content: str, tags: list[str] | None = None) -> str:
    return add_entry("note", content, tags=tags)


def write_contradiction(type_name: str, main: str = "") -> str:
    """写一条矛盾记录（仅兼容接口，实际 upsert 走 db.upsert_contradiction）"""
    return type_name


def write_decision(suggestion: str, contradiction_type: str = "") -> str:
    """写一条决策记录（仅兼容接口，实际 upsert 走 db.upsert_decision）"""
    return suggestion


def mark_done(content: str) -> bool:
    """标记决策已执行。注意：需要 user_id，这里返回 False。"""
    return False


def list_entries(entry_type: str | None = None) -> list[dict]:
    return db_list_entries(entry_type)
