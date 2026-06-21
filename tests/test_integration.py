"""用户层知识集成测试 — 确认 retriever 与 writer 通过 SQLite 协作"""

import os
import pytest
from qiushi.writer import write_note
from qiushi.db import upsert_contradiction, upsert_decision, resolve_session_user
from qiushi.retriever import KnowledgeRetriever
from qiushi.config import get_knowledge_roots


@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    """所有 db 操作指向临时目录"""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("QIUSHI_DB_PATH", str(db_path))
    # 重新导入 init_db
    import importlib
    from qiushi import db
    importlib.reload(db)
    return db_path


@pytest.mark.asyncio
async def test_retriever_still_loads_builtin(use_test_db):
    """SQLite 迁移不破坏内置知识库检索"""
    kr = KnowledgeRetriever()
    kr._ensure_loaded()
    assert len(kr.documents) > 0
    results = await kr.retrieve("矛盾")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_writer_and_identity_coexist(use_test_db):
    """writer 写 SQLite 不报错，identity 读 SQLite 也不报错"""
    write_note("矛盾是事物发展的根本动力", tags=["test"])
    upsert_contradiction("test-user", "职业选择", "收入安全 vs 自由发展")
    upsert_decision("test-user", "先业余验证MVP", "职业选择")

    from qiushi.identity import profile_summary, get_or_create_user_id
    uid = get_or_create_user_id()
    summary = profile_summary(uid)
    assert "conversation_count" in summary
