"""SQLite 存储层 — 统一数据持久化"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR


import os

DB_PATH = Path(os.environ.get("QIUSHI_DB_PATH", CONFIG_DIR / "qiushi.db"))
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """线程本地连接，避免多线程共用同一连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """建表（幂等）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
            id        TEXT PRIMARY KEY,
            type      TEXT NOT NULL,
            content   TEXT NOT NULL,
            source    TEXT DEFAULT 'qiushi',
            tags      TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contradictions (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL,
            type             TEXT NOT NULL,
            main             TEXT NOT NULL DEFAULT '',
            first_seen       TEXT NOT NULL,
            last_seen        TEXT NOT NULL,
            count            INTEGER DEFAULT 1,
            shift            INTEGER DEFAULT 0,
            last_suggestion  TEXT DEFAULT '',
            last_executed    INTEGER
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id                 TEXT PRIMARY KEY,
            user_id            TEXT NOT NULL,
            suggestion         TEXT NOT NULL,
            contradiction_type TEXT DEFAULT '',
            executed           INTEGER DEFAULT 0,
            created_at         TEXT NOT NULL,
            executed_at        TEXT,
            mention_count      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS profiles (
            user_id    TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id        TEXT PRIMARY KEY,
            session   TEXT DEFAULT '',
            feedback  TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_contradictions_user ON contradictions(user_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_user ON decisions(user_id);
        CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
    """)
    conn.commit()


# ── 工具 ──────────────────────────────────────────────────────────


def now() -> str:
    return datetime.now().isoformat()


# ── 用户身份 ──────────────────────────────────────────────────────


def get_or_create_user_id() -> str:
    import uuid
    id_path = CONFIG_DIR / "user_id"
    if id_path.exists():
        return id_path.read_text().strip()
    uid = str(uuid.uuid4())[:12]
    id_path.write_text(uid)
    return uid


def resolve_session_user(session_id: str) -> str:
    conn = _get_conn()
    row = conn.execute("SELECT user_id FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if row:
        return row["user_id"]
    user_id = get_or_create_user_id()
    conn.execute("INSERT OR IGNORE INTO sessions (session_id, user_id, created_at) VALUES (?,?,?)",
                 (session_id, user_id, now()))
    conn.commit()
    return user_id


# ── Profile ───────────────────────────────────────────────────────


def get_profile(user_id: str) -> dict:
    conn = _get_conn()
    row = conn.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    if row:
        return json.loads(row["data"])
    return {}


def save_profile(user_id: str, data: dict):
    conn = _get_conn()
    data.setdefault("conversations", [])
    data.setdefault("contradictions", [])
    data.setdefault("decisions", [])
    data.setdefault("strictness", 5)
    data.setdefault("strictness_history", [])
    data["user_id"] = user_id
    now_ts = now()
    conn.execute(
        "INSERT INTO profiles (user_id, data, created_at, updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
        (user_id, json.dumps(data, ensure_ascii=False), now_ts, now_ts),
    )
    conn.commit()


def save_conversation(user_id: str, user_input: str, reply: str, obsidian_vault: str | None = None):
    profile = get_profile(user_id)
    profile.setdefault("conversations", [])
    profile["conversations"].append({
        "user": user_input[:200],
        "assistant": reply[:200],
        "time": now(),
    })
    if len(profile["conversations"]) > 20:
        profile["conversations"] = profile["conversations"][-20:]
    save_profile(user_id, profile)

    if obsidian_vault:
        _log_obsidian(obsidian_vault, user_input, reply)


def _log_obsidian(vault: str, user_input: str, reply: str):
    from pathlib import Path
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = Path(vault) / "conversations" / "求是对话"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{today}.md"
    ts = datetime.now().strftime("%H:%M:%S")
    entry = (
        f"---\ntime: {ts}\n---\n\n"
        f"**用户** ({ts}):\n{user_input}\n\n"
        f"**求是**:\n{reply}\n\n---\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


# ── 矛盾记录 ─────────────────────────────────────────────────────


def upsert_contradiction(user_id: str, ctype: str, user_input: str = "", suggestion: str = ""):
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM contradictions WHERE user_id=? AND type=?", (user_id, ctype)
    ).fetchone()
    now_ts = now()
    if row:
        conn.execute(
            "UPDATE contradictions SET count=count+1, last_seen=?, last_suggestion=?, "
            "main=CASE WHEN ?!='' THEN ? ELSE main END WHERE id=?",
            (now_ts, suggestion, user_input[:100], user_input[:100], row["id"]),
        )
    else:
        entry_id = ctype[:4] + now_ts[-6:]
        conn.execute(
            "INSERT INTO contradictions (id, user_id, type, main, first_seen, last_seen, "
            "count, last_suggestion) VALUES (?,?,?,?,?,?,1,?)",
            (entry_id, user_id, ctype, user_input[:100], now_ts, now_ts, suggestion),
        )
    conn.commit()


def get_user_contradictions(user_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM contradictions WHERE user_id=? ORDER BY last_seen DESC", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── 决策记录 ─────────────────────────────────────────────────────


def upsert_decision(user_id: str, suggestion: str, contradiction_type: str = ""):
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM decisions WHERE user_id=? AND suggestion=?",
        (user_id, suggestion[:200]),
    ).fetchone()
    now_ts = now()
    if row:
        conn.execute(
            "UPDATE decisions SET mention_count=mention_count+1 WHERE id=?", (row["id"],)
        )
    else:
        entry_id = "dec" + now_ts[-9:]
        conn.execute(
            "INSERT INTO decisions (id, user_id, suggestion, contradiction_type, created_at) "
            "VALUES (?,?,?,?,?)",
            (entry_id, user_id, suggestion[:200], contradiction_type, now_ts),
        )
    conn.commit()


def mark_decision_done(user_id: str, suggestion_like: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM decisions WHERE user_id=? AND suggestion LIKE ?",
        (user_id, f"%{suggestion_like}%"),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE decisions SET executed=1, executed_at=? WHERE id=?",
            (now(), row["id"]),
        )
        conn.commit()
        return True
    return False


def get_user_decisions(user_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM decisions WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── 笔记 ─────────────────────────────────────────────────────────


def add_entry(entry_type: str, content: str, tags: list[str] | None = None, source: str = "qiushi") -> str:
    import hashlib
    conn = _get_conn()
    eid = hashlib.md5(content.encode()).hexdigest()[:12]
    now_ts = now()
    conn.execute(
        "INSERT OR IGNORE INTO entries (id, type, content, source, tags, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (eid, entry_type, content, source, json.dumps(tags or [], ensure_ascii=False), now_ts, now_ts),
    )
    conn.commit()
    return eid


def list_entries(entry_type: str | None = None, limit: int = 20) -> list[dict]:
    conn = _get_conn()
    if entry_type:
        rows = conn.execute(
            "SELECT * FROM entries WHERE type=? ORDER BY updated_at DESC LIMIT ?",
            (entry_type, limit),
        )
    else:
        rows = conn.execute("SELECT * FROM entries ORDER BY updated_at DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


# ── 反馈 ─────────────────────────────────────────────────────────


def save_feedback(fb_type: str, session_id: str = ""):
    import uuid
    conn = _get_conn()
    conn.execute(
        "INSERT INTO feedback (id, session, feedback, timestamp) VALUES (?,?,?,?)",
        (str(uuid.uuid4())[:8], session_id, fb_type, now()),
    )
    conn.commit()


def get_feedback_stats() -> dict:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    good = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback='good'").fetchone()[0]
    bad = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback='bad'").fetchone()[0]
    return {"total": total, "good": good, "bad": bad}


# ── Session ──────────────────────────────────────────────────────


def list_sessions() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── 初始化 ──────────────────────────────────────────────────────

init_db()
