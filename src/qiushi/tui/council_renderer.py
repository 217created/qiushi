"""多哲学人格辩论渲染器 — 三栏布局 + 打字动画"""

from __future__ import annotations

import time
import shutil
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.table import Table

from .constants import BRAND_PRIMARY, BRAND_SECONDARY, BRAND_ACCENT, BRAND_SUCCESS, BRAND_INFO, get_persona_style

TYPING_SPEED = 0.006  # 每字符秒数


def _build_layout() -> Layout:
    """自适应三栏布局"""
    tw = shutil.get_terminal_size().columns
    layout = Layout()
    layout.split_column(
        Layout(name="main", ratio=1),
        Layout(name="prompt_bar", size=1),
    )
    if tw >= 120:
        layout["main"].split_row(
            Layout(name="personas_panel", size=28),
            Layout(name="debate_view", ratio=3),
            Layout(name="active_panel", size=34),
        )
    elif tw >= 90:
        layout["main"].split_row(
            Layout(name="personas_panel", size=22),
            Layout(name="debate_view", ratio=3),
            Layout(name="active_panel", size=28),
        )
    else:
        layout["main"].split_row(
            Layout(name="personas_panel", size=18),
            Layout(name="debate_view", ratio=1),
        )
    return layout


def _build_personas_panel(council_results: list[dict], current_name: str | None = None) -> Panel:
    """左侧：哲学人格列表"""
    lines = []
    for r in council_results:
        name = r.get("name", "")
        style = get_persona_style(name)
        if r.get("error"):
            lines.append(f"[dim]○ {style['emoji']} {name}[/dim]\n  [red]✗ 失败[/red]")
        elif current_name and name == current_name:
            lines.append(f"[bold {style['color']}]● {style['emoji']} {name}[/bold {style['color']}]")
        else:
            lines.append(f"[{style['color']}]● {style['emoji']} {name}[/{style['color']}]")
        lines.append("")  # spacing
    return Panel(
        "\n".join(lines[:-1]),
        title="[bold]哲学人格[/bold]",
        border_style=BRAND_PRIMARY,
        padding=(1, 1),
    )


def _build_debate_panel(council_results: list[dict]) -> Panel:
    """中间：各人格的观点"""
    parts = []
    for r in council_results:
        name = r.get("name", "")
        reply = r.get("reply", "")
        style = get_persona_style(name)
        if r.get("error"):
            continue
        # 取前 300 字作为摘要
        preview = reply[:300] + ("..." if len(reply) > 300 else "")
        parts.append(f"[bold {style['color']}]{style['emoji']} {name}[/bold {style['color']}]")
        parts.append(preview)
        parts.append("")
    return Panel(
        "\n".join(parts),
        title="[bold]辩论观点[/bold]",
        border_style=BRAND_SECONDARY,
        padding=(1, 1),
    )


def _build_active_panel(entry: dict | None = None) -> Panel:
    """右侧：当前发言的人格详情"""
    if not entry or entry.get("error"):
        return Panel(
            Align.center("\n\n[dim]等待辩论...[/dim]", vertical="middle"),
            title="[bold]当前发言[/bold]",
            border_style="gray50",
        )
    name = entry.get("name", "")
    reply = entry.get("reply", "")
    style = get_persona_style(name)

    lines = [
        f"{style['emoji']} [bold {style['color']}]{name}[/bold {style['color']}]",
        "",
    ]
    if reply:
        lines.append(reply[:500])

    return Panel(
        "\n".join(lines),
        title="[bold]当前发言[/bold]",
        border_style=style["color"],
        padding=(1, 1),
    )


def _build_summary_panel(synthesis: str) -> Panel:
    """共识与分歧面板"""
    if not synthesis:
        return Panel("[dim]无综合结论[/dim]", title="[bold]总结[/bold]", border_style=BRAND_PRIMARY)
    return Panel(
        synthesis.strip(),
        title=f"[bold {BRAND_ACCENT}]══ 共识与分歧 ══[/bold {BRAND_ACCENT}]",
        border_style=BRAND_ACCENT,
        padding=(1, 2),
    )


def render_council_debate(
    council_results: list[dict],
    synthesis: str,
    console: Console | None = None,
) -> None:
    """多哲学人格辩论动画 + 持久摘要"""
    c = console or Console()
    valid = [r for r in council_results if not r.get("error")]

    if not valid:
        c.print("[red]辩论失败：无有效结果[/red]")
        return

    # 动画阶段
    with Live(console=c, screen=True, auto_refresh=False) as live:
        revealed = []
        for r in valid:
            revealed.append(r)
            layout = _build_layout()
            layout["personas_panel"].update(_build_personas_panel(council_results, r.get("name")))
            layout["debate_view"].update(_build_debate_panel(revealed))
            if layout["main"].get("active_panel") is not None:
                layout["active_panel"].update(_build_active_panel(r))

            live.update(layout)
            live.refresh()

            # 打字动画
            reply_text = r.get("reply", "")
            if reply_text:
                delay = min(len(reply_text) * TYPING_SPEED, 2.0)
                time.sleep(delay)
            else:
                time.sleep(0.3)

        # 最终：总结面板
        final_layout = _build_layout()
        final_layout["personas_panel"].update(_build_personas_panel(council_results))
        final_layout["debate_view"].update(_build_summary_panel(synthesis))
        if final_layout["main"].get("active_panel") is not None:
            final_layout["active_panel"].update(
                Panel(
                    Align.center(
                        f"\n\n[bold {BRAND_PRIMARY}]辩论完成[/bold {BRAND_PRIMARY}]",
                        vertical="middle",
                    ),
                    border_style=BRAND_PRIMARY,
                )
            )
        live.update(final_layout)
        live.refresh()
        time.sleep(1.5)

    # 持久摘要
    render_council_summary(council_results, synthesis, console=c)


def render_council_summary(
    council_results: list[dict],
    synthesis: str,
    console: Console | None = None,
) -> None:
    """持久摘要面板 — 放在对话历史中供回顾"""
    c = console or Console()
    tw = shutil.get_terminal_size().columns

    parts = []
    for r in council_results:
        name = r.get("name", "")
        reply = r.get("reply", "")
        style = get_persona_style(name)
        if r.get("error"):
            parts.append(f"[red]{style['emoji']} {name}: 失败[/red]")
            continue
        # 提取第一段
        first_para = reply.strip().split("\n\n")[0][:200]
        parts.append(f"[bold {style['color']}]{style['emoji']} {name}[/bold {style['color']}]")
        parts.append(f"  [dim]{first_para}[/dim]")

    # 组装
    if tw >= 60:
        col1 = "\n".join(parts)
        total_text = col1
    else:
        total_text = "\n".join(parts)

    panel = Panel(
        total_text,
        title=f"[bold {BRAND_PRIMARY}]辩论总结[/bold {BRAND_PRIMARY}]",
        border_style=BRAND_PRIMARY,
        padding=(1, 2),
        subtitle="[dim]各哲学人格的核心观点[/dim]",
    )
    c.print()
    c.print(panel)

    if synthesis:
        c.print()
        c.print(_build_summary_panel(synthesis))
    c.print()
