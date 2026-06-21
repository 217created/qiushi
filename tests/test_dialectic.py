"""对话辩证测试"""

from qiushi.dialectic import DialecticSession


def test_dialectic_session_initialized():
    s = DialecticSession(max_rounds=3)
    assert s.max_rounds == 3
    assert s.round == 0
    assert len(s.history) == 0


def test_dialectic_session_save_load(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    # 使用临时目录
    monkeypatch.setattr("qiushi.dialectic._SESSION_DIR", tmp_path)
    s = DialecticSession(max_rounds=3, session_id="test-001")
    s._question = "该不该辞职"
    s.round = 1
    s.history = [{"role": "user", "content": "该不该辞职"}]
    s.save()

    # 验证文件存在
    assert (tmp_path / "test-001.json").exists()

    # 加载
    loaded = DialecticSession.load("test-001")
    assert loaded is not None
    assert loaded._question == "该不该辞职"
    assert loaded.round == 1
    assert len(loaded.history) == 1


def test_dialectic_list_sessions(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    monkeypatch.setattr("qiushi.dialectic._SESSION_DIR", tmp_path)
    s = DialecticSession(max_rounds=3, session_id="list-test")
    s._question = "测试问题"
    s.round = 1
    s.save()

    sessions = DialecticSession.list_sessions()
    assert len(sessions) >= 1
    assert any(ss["id"] == "list-test" for ss in sessions)


def test_dialectic_delete(tmp_path, monkeypatch):
    monkeypatch.setattr("qiushi.dialectic._SESSION_DIR", tmp_path)
    s = DialecticSession(max_rounds=3, session_id="del-test")
    s.save()
    assert (tmp_path / "del-test.json").exists()

    DialecticSession.delete("del-test")
    assert not (tmp_path / "del-test.json").exists()


def test_dialectic_synthesize():
    from qiushi.engine import ProcessResult
    s = DialecticSession(max_rounds=3)
    s.results.append(ProcessResult(
        reply="【分析】核心观点A\n【反思】考虑反方\n【总结】结论A",
        sections={"main": "核心观点A", "rebuttal": "考虑反方", "summary": "结论A"},
        knowledge_results=[], matched_concepts=[], matched_macro=None,
        matched_contradictions=[], metaphors_used=[], depth=2, auto_saved=False,
    ))

    result = s._synthesize()
    assert "辩证总结" in result
    assert "核心观点A" in result
    assert "结论A" in result
