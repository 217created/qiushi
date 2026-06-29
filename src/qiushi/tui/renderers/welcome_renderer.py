"""welcome_renderer — 任务零：欢迎页渲染器"""

from __future__ import annotations

import shutil

from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.table import Table

from ..constants import BRAND_PRIMARY, BRAND_SECONDARY, BANNER_ASCII


# ── 三栏卡片定义 ───────────────────────────────────────────────────
# (标题, 标题颜色, [(命令, 说明), ...], 目标行数)
_CARD_DEFS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("💬  基础", "grey58", [
        ("/help",   "帮助"),
        ("/new",    "新对话"),
        ("/clear",  "清屏"),
        ("/exit",   "退出"),
    ]),
    ("🧠  思辨", BRAND_PRIMARY, [
        ("/dialectic", "追问链"),
        ("/council",   "辩论"),
        ("/depth",     "分析深度"),
        ("/think",     "显推理"),
    ]),
    ("🔧  工具", BRAND_SECONDARY, [
        ("/web",     "联网搜"),
        ("/search",  "本地搜"),
        ("/profile", "画像"),
        ("/card",    "卡片"),
        ("/note",    "笔记"),
    ]),
]


class WelcomeRenderer:
    """欢迎页渲染器 — Banner + 三栏便当盒命令卡片 + 输入区"""

    def __init__(self, console: Console):
        self.console = console

    def render(self, _data: dict | None = None) -> None:
        tw = shutil.get_terminal_size().columns
        self._render_banner(tw)
        self.console.print("─" * min(tw, 100), style=Style(color="grey30"))
        self._render_cards(tw)
        self.console.print("─" * min(tw, 100), style=Style(color="grey30"))
        self.console.print()

    # ── Banner ─────────────────────────────────────────────────────

    def _render_banner(self, tw: int) -> None:
        banner_lines = BANNER_ASCII.strip("\n").split("\n")
        self.console.print()
        for line in banner_lines:
            centered = line.center(tw) if tw >= 60 else line.strip()
            self.console.print(centered, style=Style(color=BRAND_PRIMARY, bold=True))

        tagline = "以哲学思辨为框架的 AI 思考伙伴  ·  输入问题直接开始"
        self.console.print()
        rendered = tagline.center(tw) if tw >= 60 else tagline
        self.console.print(rendered, style=Style(color=BRAND_SECONDARY, dim=True))
        self.console.print()

    # ── 卡片 ───────────────────────────────────────────────────────

    def _render_cards(self, tw: int) -> None:
        if tw >= 100:
            self._render_three_column()
        elif tw >= 80:
            self._render_two_column()
        elif tw >= 60:
            self._render_inline(tw)

    def _make_card_text(self, items: list[tuple[str, str]], target_rows: int) -> str:
        """生成卡片文本，用空行填充到 target_rows 行"""
        lines: list[str] = []
        for cmd, desc in items:
            lines.append(f"[bold white]{cmd}[/bold white]  {desc}")
        while len(lines) < target_rows:
            lines.append("")
        return "\n".join(lines)

    def _render_three_column(self) -> None:
        """三栏 — 用 Rich Table.grid 保证同一行"""
        grid = Table.grid(padding=(1, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        max_rows = max(len(i) for _, _, i in _CARD_DEFS)
        panels = []
        for title, color, items in _CARD_DEFS:
            text = self._make_card_text(items, max_rows)
            panels.append(Panel(text, title=title, title_align="left", border_style=color, padding=(0, 1)))

        grid.add_row(*panels)
        self.console.print(grid)

    def _render_two_column(self) -> None:
        """两栏 — 左栏合并基础+思辨，右栏工具"""
        combined = _CARD_DEFS[0][2] + _CARD_DEFS[1][2]
        tool = _CARD_DEFS[2][2]
        max_rows = max(len(combined), len(tool))

        left = Panel(
            self._make_card_text(combined, max_rows),
            title="基础 · 思辨", title_align="left",
            border_style=BRAND_PRIMARY, padding=(0, 1),
        )
        right = Panel(
            self._make_card_text(tool, max_rows),
            title="工具", title_align="left",
            border_style=BRAND_SECONDARY, padding=(0, 1),
        )
        grid = Table.grid(padding=(1, 2))
        grid.add_column(ratio=2)
        grid.add_column(ratio=1)
        grid.add_row(left, right)
        self.console.print(grid)

    def _render_inline(self, tw: int) -> None:
        parts = []
        for title, _, items in _CARD_DEFS:
            cmds = " ".join(c for c, _ in items)
            label = title.strip()
            parts.append(f"[dim]{label}:[/dim] {cmds}")
        inline = "  │  ".join(parts)
        if len(inline) > tw - 4:
            inline = inline[:tw - 7] + "..."
        self.console.print(inline, style=Style(color="grey50"))
