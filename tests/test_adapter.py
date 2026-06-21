"""适配器测试"""

from pathlib import Path
from unittest.mock import patch, MagicMock
from qiushi.adapter import DirectoryAdapter, ObsidianAdapter, load_adapters, save_adapters


def test_directory_adapter(tmp_path):
    (tmp_path / "note1.md").write_text("# 笔记1", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "note2.md").write_text("# 笔记2", encoding="utf-8")

    adapter = DirectoryAdapter(str(tmp_path), label="test")
    assert adapter.name() == "dir:test"
    files = adapter.list_files()
    assert len(files) == 2


def test_directory_adapter_non_existent():
    adapter = DirectoryAdapter("/nonexistent/path", label="gone")
    assert adapter.list_files() == []


def test_obsidian_adapter_skips_log_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir(parents=True)
    (vault / "日常笔记.md").write_text("# 日常", encoding="utf-8")
    log_dir = vault / "conversations" / "求是对话"
    log_dir.mkdir(parents=True)
    (log_dir / "2026-06-06.md").write_text("## 对话日志", encoding="utf-8")

    adapter = ObsidianAdapter(str(vault))
    files = adapter.list_files()
    names = [f.name for f in files]
    assert "日常笔记.md" in names
    assert "2026-06-06.md" not in names


def test_obsidian_adapter_non_existent():
    adapter = ObsidianAdapter("/nonexistent/vault")
    assert adapter.list_files() == []


def test_load_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("qiushi.adapter.ADAPTERS_CONFIG", tmp_path / "adapters.json")
    (tmp_path / "notes").mkdir()
    adapters = [DirectoryAdapter(str(tmp_path / "notes"), label="mynotes")]
    save_adapters(adapters)

    # 创建 mock config，obsidian_vault 为空
    mock_config = MagicMock()
    mock_config.obsidian_vault = ""
    monkeypatch.setattr("qiushi.config.QiushiConfig.load", lambda: mock_config)

    loaded = load_adapters()
    assert len(loaded) >= 1
    assert loaded[0].name() == "dir:mynotes"
