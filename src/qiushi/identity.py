"""用户身份管理 — 全部通过 SQLite"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from .config import CONFIG_DIR
from .db import (
    get_or_create_user_id as db_get_user_id,
    resolve_session_user,
    get_profile as db_get_profile,
    save_profile as db_save_profile,
    save_conversation as db_save_conversation,
    upsert_contradiction,
    upsert_decision,
    mark_decision_done,
    get_user_contradictions,
    get_user_decisions,
    save_feedback,
    list_sessions as db_list_sessions,
)


# ── 公开接口（保持签名兼容） ──────────────────────────────────────


def get_or_create_user_id() -> str:
    return db_get_user_id()


def resolve_user_id(session_id: str) -> str:
    return resolve_session_user(session_id)


def get_profile(user_id: str) -> dict:
    return db_get_profile(user_id)


def save_profile(user_id: str, profile: dict):
    db_save_profile(user_id, profile)


def save_conversation(user_id: str, user_input: str, reply: str, obsidian_vault: str | None = None):
    db_save_conversation(user_id, user_input, reply, obsidian_vault)


def update_user_contradictions(user_id: str, contradiction_types: list[str], user_input: str, suggestion: str = ""):
    """更新矛盾记录到 SQLite"""
    for ct in contradiction_types:
        upsert_contradiction(user_id, ct, user_input, suggestion)


def update_user_decision(user_id: str, suggestion_content: str) -> bool:
    return mark_decision_done(user_id, suggestion_content)


def build_cross_session_context(profile: dict, matched_contradictions: list[str]) -> str | None:
    """从 SQLite 读取矛盾信息构建跨 session 注入"""
    user_id = profile.get("user_id", "")
    if not user_id or not matched_contradictions:
        return None

    contradictions = get_user_contradictions(user_id)
    for ctype in matched_contradictions:
        for c in contradictions:
            if c.get("type") != ctype:
                continue
            count = c.get("count", 0)
            if count < 2:
                continue

            lines = [f"注意：这个用户之前也提过「{ctype}」相关的问题（第{count}次出现）。"]
            last_suggestion = c.get("last_suggestion", "")
            if last_suggestion:
                lines.append(f"上次给出的建议是：{last_suggestion}")
            executed = c.get("last_executed")
            if executed:
                lines.append("用户上次执行了建议，先肯定他的行动。")
            elif executed == 0:
                lines.append("用户上次未执行建议，先温和询问原因，再分析。")
            else:
                lines.append("先询问上次建议的执行情况，再分析。")
            return "\n".join(lines)

    return None


def profile_summary(user_id: str) -> dict:
    """生成用户画像摘要"""
    profile = db_get_profile(user_id)
    contradictions = get_user_contradictions(user_id)
    decisions = get_user_decisions(user_id)
    conv_count = len(profile.get("conversations", []))
    total_decisions = len(decisions)
    executed_count = sum(1 for d in decisions if d.get("executed"))

    return {
        "user_id": user_id,
        "conversation_count": conv_count,
        "contradictions": contradictions,
        "decisions": decisions,
        "strictness": profile.get("strictness", 5),
        "execution_rate": f"{executed_count}/{total_decisions}" if total_decisions > 0 else "暂无",
        "created_at": profile.get("created_at", ""),
    }


def list_sessions() -> list[dict]:
    return db_list_sessions()
