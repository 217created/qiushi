"""苏格拉底追问链渲染器 — 用 Rich 做漂亮的多轮追问展示"""

from __future__ import annotations

import sys
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.columns import Columns
from rich.markdown import Markdown
import time
import shutil

from .constants import BRAND_PRIMARY, BRAND_SECONDARY, BRAND_ACCENT, get_persona_style


def render_dialectic_round(
    round_num: int,
    total_rounds: int,
    analysis: str,
    follow_up: str | None = None,
    console: Console | None = None,
) -> None:
    """渲染一轮苏格拉底追问的结果"""
    c = console or Console()

    # 轮次头
    round_text = Text()
    round_text.append(f"══ 第 {round_num}/{total_rounds} 轮 ══", style=f"bold {BRAND_PRIMARY}")

    if round_num == 1:
        round_text.append("  — 初步分析", style=f"dim {BRAND_SECONDARY}")
    else:
        round_text.append("  — 深入追问", style=f"dim {BRAND_SECONDARY}")

    c.print()
    c.print(Panel(round_text, border_style=BRAND_PRIMARY, padding=(0, 1)))

    # 分析内容
    c.print()
    c.print(Panel(
        Markdown(analysis.strip()),
        border_style=BRAND_SECONDARY,
        padding=(1, 2),
        subtitle=f"[dim]第{round_num}轮分析[/dim]",
    ))

    # 追问
    if follow_up:
        c.print()
        c.print(Panel(
            f"[bold {BRAND_ACCENT}]❓ {follow_up}[/bold {BRAND_ACCENT}]",
            border_style=BRAND_ACCENT,
            padding=(1, 2),
            title="[bold]苏格拉底追问[/bold]",
        ))


def render_dialectic_summary(synthesis: str, console: Console | None = None) -> None:
    """渲染辩证总结"""
    c = console or Console()
    c.print()
    c.print(Panel(
        Markdown(synthesis.strip()) if "══" not in synthesis else synthesis.strip(),
        border_style=BRAND_PRIMARY,
        padding=(1, 2),
        title=f"[bold {BRAND_PRIMARY}]══ 辩证总结 ══[/bold {BRAND_PRIMARY}]",
        subtitle="[dim]多轮思辨的结晶[/dim]",
    ))
    c.print()


def render_dialectic_full(
    rounds_data: list[dict],
    synthesis: str,
    console: Console | None = None,
) -> None:
    """全量渲染：展示每一轮 + 总结"""
    c = console or Console()
    tw = shutil.get_terminal_size().columns

    # 顶部概要
    total = len(rounds_data)
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("属性", style=f"bold {BRAND_PRIMARY}")
    summary_table.add_column("值")
    summary_table.add_row("轮数", str(total))
    summary_table.add_row("追问风格", "苏格拉底式")
    c.print(Panel(summary_table, border_style=BRAND_PRIMARY, padding=(1, 1)))

    # 各轮
    for i, rd in enumerate(rounds_data):
        render_dialectic_round(
            round_num=i + 1,
            total_rounds=total,
            analysis=rd.get("analysis", ""),
            follow_up=rd.get("follow_up"),
            console=c,
        )
        if i < total - 1 and tw >= 40:
            c.print(f"  [{BRAND_SECONDARY}]│[/{BRAND_SECONDARY}]")
            c.print(f"  [{BRAND_SECONDARY}]│  等待你的回应...[/{BRAND_SECONDARY}]")
            c.print(f"  [{BRAND_SECONDARY}]│[/{BRAND_SECONDARY}]")

    # 总结
    render_dialectic_summary(synthesis, console=c)


def is_interactive() -> bool:
    """检测当前是否在交互式终端中"""
    return sys.stdin.isatty() and sys.stdout.isatty()


async def prompt_user(message: str = "你的回答") -> str:
    """获取用户输入，自动检测交互环境"""
    from prompt_toolkit import PromptSession
    
    if not is_interactive():
        print(f"\n{message}: ", end="", flush=True)
        return sys.stdin.readline().strip()
    
    try:
        session = PromptSession()
        result = await session.prompt_async(f"\n[bold]{message}[/bold] > ")
        return result.strip()
    except Exception:
        # 回退
        try:
            return input(f"\n{message}: ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""
