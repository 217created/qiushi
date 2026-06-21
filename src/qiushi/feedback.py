"""事后反馈记录模块 — 通过 SQLite"""

from __future__ import annotations

from .db import save_feedback as db_save_feedback, get_feedback_stats as db_stats


def record_feedback(session_id: str, feedback: str, question: str = "", answer_summary: str = ""):
    """记录一次反馈到 SQLite"""
    db_save_feedback(feedback, session_id)


def get_feedback_stats() -> dict:
    """返回反馈统计"""
    return db_stats()
