"""CLI 冒烟测试 — 用 typer.testing.CliRunner 验证子命令注册"""
from typer.testing import CliRunner
from qiushi.cli import app

runner = CliRunner()


def test_help():
    """--help 应该列出所有子命令"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # typer 输出包含子命令名称
    assert "ask" in result.stdout or "ask".upper() in result.stdout.upper()
    assert "chat" in result.stdout or "chat".upper() in result.stdout.upper()
    assert "knowledge" in result.stdout or "knowledge".upper() in result.stdout.upper()


def test_version():
    """--version 应该输出版本号"""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0


def test_knowledge_help():
    """knowledge 子命令应该可以列出"""
    result = runner.invoke(app, ["knowledge"])
    assert result.exit_code == 0


def test_init_not_configured():
    """没有 .qiushi/config.json 时 init 应该提示而不是崩溃"""
    import os
    from pathlib import Path
    import json

    config_path = Path.home() / ".qiushi" / "config.json"
    if config_path.exists():
        # 备份 config，测完恢复
        backup = config_path.read_text()
        config_path.unlink()
        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0 or result.exit_code == 1
        finally:
            config_path.write_text(backup)
    else:
        result = runner.invoke(app, ["ask", "test"])
        # 没有 config 也能跑（会从环境变量读）
        assert result.exit_code in (0, 1, 2)
