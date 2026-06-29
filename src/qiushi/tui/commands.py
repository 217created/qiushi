"""commands — 斜杠命令注册表与处理器"""

from __future__ import annotations

from typing import Callable, Optional

from .state import CommandContext
from ..engine import QiuShiEngine


# ── 注册表 ─────────────────────────────────────────────────────

_handlers: dict[str, Callable] = {}


def register(name: str):
    def decorator(func: Callable):
        _handlers[name] = func
        return func
    return decorator


async def dispatch(raw: str, ctx: CommandContext) -> tuple[bool, bool]:
    """执行斜杠命令。返回 (handled, should_exit)"""
    parts = raw.strip().split(maxsplit=1)
    cmd_name = parts[0][1:].lower()
    arg_line = parts[1] if len(parts) > 1 else ""

    handler = _handlers.get(cmd_name)
    if handler:
        result = handler(arg_line, ctx)
        if hasattr(result, "__await__"):
            return await result
        return result
    else:
        ctx.console.print(f"[dim]未知命令: /{cmd_name}  (输入 /help 查看所有命令)[/dim]")
        return True, False


# ── 命令实现 ───────────────────────────────────────────────────

@register("help")
def _help(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    from .constants import HELP_TEXT
    ctx.console.print(HELP_TEXT)
    return True, False


@register("new")
def _new(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    ctx.history.clear()
    ctx.console.print("[dim]🔄 新对话，历史已清空[/dim]")
    return True, False


@register("clear")
def _clear(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    ctx.console.clear()
    from .renderers.welcome_renderer import WelcomeRenderer
    WelcomeRenderer(ctx.console).render()
    return True, False


@register("exit")
@register("quit")
def _exit(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    ctx.should_exit = True
    return True, True


@register("think")
def _think(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    ctx.show_think = not ctx.show_think
    label = "完整推理" if ctx.show_think else "简洁"
    ctx.console.print(f"[dim]✅ 切换为 {label} 模式[/dim]")
    return True, False


@register("depth")
def _depth(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    if args.isdigit():
        d = int(args)
        if 1 <= d <= 3:
            ctx.depth = d
            labels = ["快速", "标准", "深度"]
            ctx.console.print(f"[dim]🧠 分析深度 → {d}  ({labels[d-1]})[/dim]")
            return True, False
    ctx.console.print(f"[dim]用法: /depth 1|2|3  (当前: {ctx.depth})[/dim]")
    return True, False


@register("web")
async def _web(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    if not args:
        ctx.console.print("[dim]用法: /web <搜索关键词>[/dim]")
        return True, False

    from .constants import LOADING_PHASES
    if ctx.searcher is None:
        ctx.searcher = WebSearcher()

    with ctx.console.status(LOADING_PHASES["searching"][0], spinner=LOADING_PHASES["searching"][1]):
        results = await ctx.searcher.search(args)
        context = ctx.searcher.format_context(results)

    if not results:
        ctx.console.print("[yellow]⚠ 未搜索到结果[/yellow]")
        return True, False

    combined = f"{args}\n\n以下是相关搜索结果：\n{context}\n\n请基于以上信息进行分析。"
    ctx.history.append({"role": "user", "content": combined})
    if len(ctx.history) > 50:
        ctx.history = ctx.history[-50:]

    with ctx.console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
        result = await ctx.engine.process_with_result(ctx.sid, combined, depth=ctx.depth)

    from rich.markdown import Markdown
    from rich.panel import Panel
    from .constants import BRAND_PRIMARY
    ctx.console.print(Panel(
        Markdown(result.public_text),
        title=f"[bold]求是分析[/bold]",
        border_style=BRAND_PRIMARY,
        padding=(1, 2),
    ))
    return True, False


@register("search")
def _search(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    if not args:
        ctx.console.print("[dim]用法: /search <关键词> — 在本地知识库中搜索[/dim]")
        return True, False

    import asyncio
    loop = _get_or_create_loop()

    async def _do_search():
        from ..retriever import KnowledgeRetriever
        kr = KnowledgeRetriever()
        return await kr.retrieve(args, top_k=5)

    from .constants import LOADING_PHASES
    with ctx.console.status(LOADING_PHASES["searching"][0], spinner=LOADING_PHASES["searching"][1]):
        results = loop.run_until_complete(_do_search())

    if not results:
        ctx.console.print(f'[yellow]⚠ 本地知识库中未找到 "{args}" 相关内容[/yellow]')
        ctx.console.print("[dim]提示: 试试 /web <关键词> 搜索网络，或 /knowledge add --path <路径> 添加本地知识[/dim]")
        return True, False

    from .constants import BRAND_INFO
    from rich.markdown import Markdown
    from rich.panel import Panel
    lines = []
    for i, r in enumerate(results, 1):
        preview = r.get("content", "")[:150]
        source = r.get("source", "")
        score = r.get("score", 0)
        lines.append(f"[bold {BRAND_INFO}]{i}. {preview}[/bold {BRAND_INFO}]")
        if source:
            lines.append(f"   [dim]📄 {source} (相关度: {score:.0%})[/dim]")
        lines.append("")

    ctx.console.print(Panel(
        "\n".join(lines),
        title=f"[bold]知识库搜索: {args}[/bold]",
        border_style=BRAND_INFO,
        padding=(1, 2),
    ))
    return True, False


@register("profile")
def _profile(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    import asyncio
    from ..identity import profile_summary, get_or_create_user_id
    from rich.table import Table
    from rich.panel import Panel
    from .constants import BRAND_PRIMARY, BRAND_ACCENT

    uid = get_or_create_user_id()
    summary = profile_summary(uid)

    t = Table(box=None, header_style=f"bold {BRAND_PRIMARY}")
    t.add_column("维度")
    t.add_column("值")
    t.add_row("对话次数", str(summary["conversation_count"]))
    t.add_row("严厉指数", f"{summary['strictness']}")
    t.add_row("决策执行率", f"{summary['execution_rate']}")
    ctx.console.print()
    ctx.console.print(Panel(t, title="[bold]思维画像[/bold]", border_style=BRAND_PRIMARY, padding=(1, 1)))
    ctx.console.print()
    return True, False


@register("card")
def _card(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    from ..card import generate_card
    from rich.markdown import Markdown
    from rich.panel import Panel
    from .constants import BRAND_PRIMARY
    result = generate_card(args)
    ctx.console.print()
    ctx.console.print(Panel(Markdown(result), border_style=BRAND_PRIMARY, padding=(1, 2), title="[bold]思辨卡片[/bold]"))
    ctx.console.print()
    return True, False


@register("note")
def _note(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    from ..writer import write_note
    if args:
        write_note(args)
        ctx.console.print("[green]✅ 笔记已保存[/green]")
    else:
        ctx.console.print("[dim]用法: /note <笔记内容>[/dim]")
    return True, False


@register("done")
def _done(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    """标记决策已执行"""
    from ..db import mark_decision_done, get_user_decisions
    from ..identity import get_or_create_user_id, update_user_decision

    if not args:
        uid = get_or_create_user_id()
        decisions = get_user_decisions(uid)
        pending = [d for d in decisions if not d.get("executed")]
        if not pending:
            ctx.console.print("[dim]没有待执行的决策[/dim]")
            return True, False
        ctx.console.print("[bold]待执行决策：[/bold]")
        for i, d in enumerate(pending, 1):
            ctx.console.print(f"  {i}. {d.get('suggestion','')[:60]}")
        ctx.console.print("[dim]使用 /done <关键词> 标记已执行[/dim]")
        return True, False

    uid = get_or_create_user_id()
    result = mark_decision_done(uid, args)
    if result:
        update_user_decision(uid, args)
        ctx.console.print("[green]✅ 已标记为已执行[/green]")
    else:
        ctx.console.print("[yellow]未找到匹配的决策，试试 /done 查看待执行列表[/yellow]")
    return True, False


@register("dialectic")
async def _dialectic(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    """苏格拉底追问链"""
    parts = args.split(maxsplit=1)
    rounds = int(parts[0]) if parts and parts[0].isdigit() else 2
    question = parts[1] if len(parts) > 1 else ""
    if not question:
        ctx.console.print("[dim]用法: /dialectic <轮数> <问题>[/dim]")
        ctx.console.print("[dim]例如: /dialectic 3 该不该辞职[/dim]")
        return True, False
    rounds = min(max(rounds, 1), 5)
    from ..cli import _run_dialectic_tui
    from prompt_toolkit import PromptSession
    session_ps = PromptSession()
    await _run_dialectic_tui(ctx.engine, ctx.sid, question, rounds, ctx.depth, session_ps)
    return True, False


@register("council")
async def _council(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    """多哲学人格辩论 — 两步：选流派 → 输问题"""
    from ..config import DEFAULT_PERSONAE

    active = [p for p in DEFAULT_PERSONAE if p.get("active", True)]

    if not args:
        ctx.console.print(f"\n[bold]选择辩论流派（输入编号，空格分隔）：[/bold]\n")
        from rich.table import Table
        from rich import box as rbox
        group_colors = {
            "西方·古代": "#B8846B",
            "西方·近代": "#7B8B9B",
            "西方·现代": "#6B5B7B",
            "东方": "#C46B6B",
            "现代批判": "#7B9B7B",
            "实践哲学": "#8B7D5B",
        }
        # 单表格 + 按组着色
        t = Table(box=rbox.SIMPLE, padding=(0, 1), expand=True)
        t.add_column("", style="grey50", width=3)
        t.add_column("编号", style="grey50", width=4)
        t.add_column("流派", no_wrap=True)
        t.add_column("描述", ratio=1)
        last_group = None
        for p in active:
            i = active.index(p) + 1
            color = group_colors.get(p["group"], "grey58")
            t.add_row(f"[{color}]●[/{color}]", str(i), f"[bold {color}]{p['name']}[/bold {color}]", f"[grey70]{p['desc']}[/grey70]")
        ctx.console.print(t)
        ctx.console.print(f"\n[dim]示例: /council 1 3 8  (选 2-5 个流派)[/dim]")
        ctx.console.print(f"[dim]选好后，直接输入问题开始辩论[/dim]")
        return True, False

    parts = args.split()
    indices = []
    for p in parts:
        if p.isdigit():
            i = int(p)
            if 1 <= i <= len(active):
                indices.append(i - 1)

    if len(indices) < 2:
        ctx.console.print("[dim]请至少选 2 个流派，例如: /council 1 3 8[/dim]")
        return True, False

    selected = [(active[i]["name"], active[i]["desc"]) for i in indices]
    names = [s[0] for s in selected]
    ctx.console.print(f"[dim]已选: {' · '.join(names)}[/dim]")
    ctx.console.print(f"[dim]请输入你的问题开始辩论[/dim]")

    ctx.pending_council_personae = selected
    return True, False


@register("personae")
def _personae(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    from .constants import PERSONA_STYLE
    ctx.console.print(f"[bold]可用哲学人格[/bold]")
    for name in PERSONA_STYLE:
        style = PERSONA_STYLE[name]
        ctx.console.print(f"  {style['emoji']} [{style['color']}]{name}[/{style['color']}]")
    return True, False


@register("history")
def _history(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    parts = args.split()
    show_full = "full" in parts or "all" in parts
    n_parts = [p for p in parts if p.isdigit()]
    n = int(n_parts[0]) if n_parts else 10
    n = min(max(n, 1), 50)

    if not ctx.history:
        ctx.console.print("[dim]暂无对话历史[/dim]")
        return True, False

    recent = ctx.history[-n:]
    from rich.panel import Panel
    from .constants import BRAND_PRIMARY, BRAND_SECONDARY

    if show_full:
        ctx.console.print(f"\n[bold]最近 {len(recent)} 条对话（完整）[/bold]\n")
        for i, entry in enumerate(recent, 1):
            role = entry.get("role", "user")
            content = entry.get("content", "")
            icon = "👤" if role == "user" else "🧠"
            role_name = "你" if role == "user" else "求是"
            border = BRAND_PRIMARY if role == "user" else BRAND_SECONDARY
            ctx.console.print(Panel(content, title=f"[bold]{icon} {role_name} (#{i})[/bold]", border_style=border, padding=(1, 2)))
            ctx.console.print()
    else:
        max_chars = 120
        ctx.console.print(f"[bold]最近 {len(recent)} 条对话：[/bold]")
        for i, entry in enumerate(recent, 1):
            role = entry.get("role", "user")
            content = entry.get("content", "")
            icon = "👤" if role == "user" else "🧠"
            if len(content) > max_chars:
                content = content[:max_chars] + f" [dim]...（共{len(content)}字）[/dim]"
            ctx.console.print(f"  {icon} {content}")
    return True, False


@register("knowledge")
def _knowledge(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    parts = args.split(maxsplit=2)
    action = parts[0] if parts else ""
    if action == "list":
        from pathlib import Path as _Path
        from ..config import USER_KNOWLEDGE_DIR
        if not USER_KNOWLEDGE_DIR.exists():
            ctx.console.print("[dim]用户知识库为空[/dim]")
            return True, False
        from rich.table import Table
        t = Table(box=None, header_style=f"bold")
        t.add_column("目录/文件")
        t.add_column("段落")
        total = 0
        for subdir in sorted(USER_KNOWLEDGE_DIR.iterdir()):
            if subdir.is_dir():
                for f in sorted(subdir.glob("*.md")):
                    paras = len(f.read_text(encoding="utf-8").split("\n\n"))
                    total += paras
                    t.add_row(f"  {subdir.name}/{f.name}", str(paras))
        t.add_row(f"[bold]合计[/bold]", str(total))
        ctx.console.print(t)
        return True, False

    if action == "reload":
        from ..retriever import KnowledgeRetriever
        kr = KnowledgeRetriever()
        kr.reload()
        ctx.console.print("[green]✅ 知识库已重新加载[/green]")
        return True, False

    ctx.console.print(f"[bold]知识库管理[/bold]")
    ctx.console.print("  /knowledge list      列出已加载的知识")
    ctx.console.print("  /knowledge reload    重新加载知识库")
    return True, False


@register("scenario")
def _scenario(args: str, ctx: CommandContext) -> tuple[bool, bool]:
    valid = ["general", "career", "relationship", "management"]
    if args in valid:
        ctx.engine._scenario = args
        ctx.scenario = args
        name_map = {"general": "通用", "career": "职业", "relationship": "关系", "management": "管理"}
        ctx.console.print(f"[green]✅ 场景已切换至: {name_map.get(args, args)}[/green]")
        return True, False
    ctx.console.print(f"[dim]无效场景。可选: {', '.join(valid)}[/dim]")
    return True, False


@register("version")
def _version(_args: str, ctx: CommandContext) -> tuple[bool, bool]:
    from .. import __version__
    ctx.console.print(f"[dim]求是 v{__version__}[/dim]")
    return True, False


# ── 工具 ───────────────────────────────────────────────────────

_loop_cache = None

def _get_or_create_loop():
    """获取或创建事件循环（用于同步上下文中执行异步搜索）"""
    global _loop_cache
    import asyncio
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        if _loop_cache is None or _loop_cache.is_closed():
            _loop_cache = asyncio.new_event_loop()
        return _loop_cache
