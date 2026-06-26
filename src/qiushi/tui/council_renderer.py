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
    elif tw >= 60:
        layout["main"].split_row(
            Layout(name="personas_panel", size=18),
            Layout(name="debate_view", ratio=1),
        )
    else:
        # 窄屏 (<60)：只显示辩论观点面板
        layout["main"].split_row(
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
    """中间：各人格的观点（窄屏自适应 padding）"""
    tw = shutil.get_terminal_size().columns
    _p = (0, 1) if tw < 60 else (1, 1)
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
        padding=_p,
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
    """共识与分歧面板（自适应 padding）"""
    tw = shutil.get_terminal_size().columns
    v_pad, h_pad = (0, 1) if tw < 60 else (1, 2)
    if not synthesis:
        return Panel("[dim]无综合结论[/dim]", title="[bold]总结[/bold]", border_style=BRAND_PRIMARY)
    return Panel(
        synthesis.strip(),
        title=f"[bold {BRAND_ACCENT}]══ 结构化分析总结 ══[/bold {BRAND_ACCENT}]",
        border_style=BRAND_ACCENT,
        padding=(v_pad, h_pad),
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
            has_personas = layout["main"].get("personas_panel") is not None
            has_active = layout["main"].get("active_panel") is not None
            if has_personas:
                layout["personas_panel"].update(_build_personas_panel(council_results, r.get("name")))
            layout["debate_view"].update(_build_debate_panel(revealed))
            if has_active:
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
        has_personas = final_layout["main"].get("personas_panel") is not None
        has_active = final_layout["main"].get("active_panel") is not None
        if has_personas:
            final_layout["personas_panel"].update(_build_personas_panel(council_results))
        final_layout["debate_view"].update(_build_summary_panel(synthesis))
        if has_active:
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
    """持久摘要面板 — 完整展示各流派观点 + 共识分歧"""
    c = console or Console()
    tw = shutil.get_terminal_size().columns
    _v, _h = (0, 1) if tw < 60 else (1, 2)

    has_error = any(r.get("error") for r in council_results)
    has_short = tw < 50

    for r in council_results:
        name = r.get("name", "")
        reply = r.get("reply", "")
        style = get_persona_style(name)
        if r.get("error"):
            c.print(Panel(
                f"[red]{style['emoji']} {name}: 失败 ({r['error']})[/red]",
                border_style="red",
            ))
            continue
        # 超窄屏只展示摘要
        display_text = reply.strip()
        if has_short and len(display_text) > 200:
            display_text = display_text[:200] + "\n\n[dim]...（完整内容见上方辩论动画）[/dim]"
        c.print(Panel(
            display_text,
            title=f"[bold {style['color']}]{style['emoji']} {name}[/bold {style['color']}]",
            border_style=style["color"],
            padding=(_v, _h),
        ))
        c.print()

    if synthesis:
        c.print(_build_summary_panel(synthesis))
    # 辩论完成提示
    sep = "─" * min(tw - 2, 50)
    c.print(f"[dim]{sep}[/dim]")
    c.print(f"[dim]{'🔚 辩论完成' if tw >= 50 else '🔚 完成'} · /help 查看命令 · 继续输入即可对话[/dim]")
    c.print()
