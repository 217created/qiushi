"""外部知识源适配器 — 只读，用于知识检索"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from .config import CONFIG_DIR


ADAPTERS_CONFIG = CONFIG_DIR / "adapters.json"

# 求是自己写的日志目录，适配器跳过避免自引用
_LOG_EXCLUDE = "/conversations/求是对话"


class KnowledgeAdapter(ABC):
    """外部知识源适配器接口（只读）"""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def list_files(self) -> list[Path]:
        """返回所有可读的 .md 文件列表"""
        ...

    def watch(self, callback: Callable[[list[Path]], None]) -> None:
        """可选：监听文件变化。默认不实现。"""
        pass


class DirectoryAdapter(KnowledgeAdapter):
    """读取本地目录下的 .md 文件"""

    def __init__(self, path: str, label: str = ""):
        self._path = Path(path).expanduser().resolve()
        self._label = label or self._path.name

    def name(self) -> str:
        return f"dir:{self._label}"

    def list_files(self) -> list[Path]:
        if not self._path.is_dir():
            return []
        return sorted(self._path.rglob("*.md"))


class ObsidianAdapter(KnowledgeAdapter):
    """读取 Obsidian vault 中的笔记，跳过求是自己写的对话日志"""

    def __init__(self, vault_path: str):
        self._path = Path(vault_path).expanduser().resolve()

    def name(self) -> str:
        return "obsidian"

    def list_files(self) -> list[Path]:
        if not self._path.is_dir():
            return []
        all_files = self._path.rglob("*.md")
        # 跳过求是对话日志，避免自引用
        return sorted(f for f in all_files if _LOG_EXCLUDE not in str(f))


def load_adapters() -> list[KnowledgeAdapter]:
    """从 ~/.qiushi/adapters.json 加载适配器配置，自动注册配置中的 Obsidian vault"""
    adapters: list[KnowledgeAdapter] = []

    # 从 adapters.json 加载
    if ADAPTERS_CONFIG.exists():
        data = json.loads(ADAPTERS_CONFIG.read_text(encoding="utf-8"))
        for entry in data.get("adapters", []):
            kind = entry.get("type", "")
            path = entry.get("path", "")
            if kind == "dir":
                adapters.append(DirectoryAdapter(path, label=entry.get("label", "")))
            elif kind == "obsidian":
                adapters.append(ObsidianAdapter(path))

    # 自动注册配置中的 Obsidian vault（如果还没注册）
    from .config import QiushiConfig
    config = QiushiConfig.load()
    vault = config.obsidian_vault
    if vault:
        vault_path = str(Path(vault).expanduser().resolve())
        already = any(
            isinstance(a, ObsidianAdapter) and str(a._path) == vault_path
            for a in adapters
        )
        if not already:
            adapters.append(ObsidianAdapter(vault))

    return adapters


def save_adapters(adapters: list[KnowledgeAdapter]):
    """保存适配器配置（不保存自动注册的 vault，它由 config 驱动）"""
    data = {"adapters": []}
    for a in adapters:
        if isinstance(a, DirectoryAdapter):
            data["adapters"].append({"type": "dir", "path": str(a._path), "label": a._label})
        elif isinstance(a, ObsidianAdapter):
            # 不保存自动注册的 vault（由 config 管理）
            from .config import QiushiConfig
            config = QiushiConfig.load()
            if config.obsidian_vault:
                vault_path = str(Path(config.obsidian_vault).expanduser().resolve())
                if str(a._path) == vault_path:
                    continue
            data["adapters"].append({"type": "obsidian", "path": str(a._path)})
    ADAPTERS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ADAPTERS_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
