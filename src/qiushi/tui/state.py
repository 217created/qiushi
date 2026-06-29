"""state — 交互会话的上下文与状态定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

from ..engine import QiuShiEngine
from .searcher import WebSearcher


@dataclass
class CommandContext:
    """斜杠命令的上下文 — 承载交互会话中的所有可读写状态"""
    console: Console
    engine: QiuShiEngine
    sid: str
    history: list = field(default_factory=list)
    searcher: Optional[WebSearcher] = None

    # 可配置状态（命令处理时可以修改）
    depth: int = 2
    show_think: bool = False
    show_explain: bool = False
    scenario: str = "general"

    # 控制信号
    should_exit: bool = False

    # 多步命令状态
    pending_council_personae: Optional[list] = None  # PR: /council 两步选流派
