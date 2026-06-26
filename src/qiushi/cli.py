"""求是 CLI — 完整 TUI 版"""
# /// script
# dependencies = ["typer", "rich", "prompt-toolkit", "httpx"]
# ///

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from .engine import QiuShiEngine, ProcessResult
from .config import QiushiConfig, CONFIG_PATH, CONFIG_DIR
from .dialectic import DialecticSession
from .card import generate_card
from .llm import LLMError
from .writer import write_note
from .db import upsert_decision, mark_decision_done, list_entries as db_list_entries
from .adapter import DirectoryAdapter, ObsidianAdapter, load_adapters, save_adapters
from .identity import profile_summary, get_or_create_user_id, update_user_decision
from .config import USER_KNOWLEDGE_DIR
from .prompt_builder import PromptBuilder

# ── TUI 模块 ────────────────────────────────────────────────────
from .tui.constants import (
    BRAND_PRIMARY, BRAND_SECONDARY, BRAND_ACCENT, BRAND_INFO,
    WELCOME_BANNER, HELP_TEXT, LOADING_PHASES, get_persona_style,
)
from .tui.dialectic_renderer import (
    render_dialectic_round, render_dialectic_summary, render_dialectic_full,
    prompt_user,
)
from .tui.council_renderer import render_council_debate, render_council_summary
from .tui.searcher import WebSearcher

logger = logging.getLogger(__name__)

# ── 全局 ─────────────────────────────────────────────────────────
console = Console(highlight=False)
app = typer.Typer(name="qiushi", help="求是 — 以哲学思辨为框架的 AI 思考伙伴", no_args_is_help=True)
HISTORY_FILE = os.path.expanduser("~/.qiushi_history")


def _version_callback(value: bool):
    if value:
        from . import __version__
        typer.echo(f"qiushi v{__version__}")
        raise typer.Exit()


@app.callback()
def _main(version: bool = typer.Option(False, "--version", "-v", help="显示版本号", callback=_version_callback)):
    pass


def _detect_obsidian_vault() -> str | None:
    candidates = [
        Path.home() / "Documents/Obsidian Vault",
        Path.home() / "Obsidian",
        Path.home() / "Documents/Obsidian",
    ]
    for p in candidates:
        if (p / ".obsidian").is_dir():
            return str(p)
    return None


def _check_config() -> list[str]:
    warnings: list[str] = []
    config = QiushiConfig.load()
    if not config.llm.api_key and not config.get_effective_api_key():
        provider = config.llm.provider
        if provider != "ollama":
            env_var = f"{provider.upper()}_API_KEY"
            warnings.append(f"未配置 API Key。请设置环境变量 {env_var}")
    return warnings


def _confirm_api():
    """确保 API 可用"""
    config = QiushiConfig.load()
    if not config.get_effective_api_key() and config.llm.provider != "ollama":
        console.print(f"[bold {BRAND_ERROR}]✗ 未配置 API Key[/bold {BRAND_ERROR}]")
        console.print(f"[dim]  运行 qiushi init 配置，或设置环境变量 {config.llm.provider.upper()}_API_KEY[/dim]")
        raise typer.Exit(1)


def _make_banner_terminal():
    """终端自适应的欢迎横幅"""
    tw = shutil.get_terminal_size().columns
    if tw < 60:
        return f"[bold {BRAND_PRIMARY}]求是 — 思辨，然后行动。[/bold {BRAND_PRIMARY}]\n[dim]/help 查看命令[/dim]"
    return WELCOME_BANNER


# ═══════════════════════════════════════════════════════════════════
#  交互式 TUI (chat 命令)
# ═══════════════════════════════════════════════════════════════════

@app.command()
def chat(
    message: str | None = typer.Argument(None, help="直接提问（不进入交互模式）"),
    session: str | None = typer.Option(None, "--session", "-s", help="会话 ID"),
    depth: int = typer.Option(2, "--depth", "-d", help="分析深度 1-3"),
    think: bool = typer.Option(False, "--think", "-t", help="显示完整推理过程"),
    explain: bool = typer.Option(False, "--explain", "-e", help="展示内部决策信息"),
    scenario: str = typer.Option("general", "--scenario", "-c", help="场景 general/career/relationship/management"),
):
    """交互式对话或单次提问（带 TUI 效果）"""
    _confirm_api()
    config = QiushiConfig.load()
    vault = config.obsidian_vault or _detect_obsidian_vault()
    sid = session or str(uuid.uuid4())[:8]

    if message:
        # 单次提问（TUI 风格输出）
        asyncio.run(_single_ask_tui(message, sid, config, vault, depth, think, explain, scenario))
    else:
        # 交互式 TUI
        asyncio.run(_interactive_tui(sid, config, vault, depth, think, explain, scenario))


async def _single_ask_tui(
    question: str, sid: str, config: QiushiConfig, vault: str | None,
    depth: int, think: bool, explain: bool, scenario: str,
):
    """单次提问，带 TUI 效果"""
    console.print()
    engine = QiuShiEngine(config=config, obsidian_vault=vault)
    async with engine:
        engine._scenario = scenario

        with console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
            result = await engine.process_with_result(sid, question, depth=depth)

        if explain:
            console.print(result.to_explain_text(question))
        elif think:
            # 带 Markdown 渲染的思考模式
            md = Markdown(result.full_text)
            console.print(Panel(md, border_style=BRAND_PRIMARY, padding=(1, 2)))
        else:
            md = Markdown(result.public_text)
            console.print(Panel(md, border_style=BRAND_SECONDARY, padding=(1, 2), subtitle="[dim]求是回答[/dim]"))
    console.print()


async def _interactive_tui(
    sid: str, config: QiushiConfig, vault: str | None,
    depth: int, think: bool, explain: bool, scenario: str,
):
    """完整的交互式 TUI"""
    console.clear()
    console.print(_make_banner_terminal())

    engine = QiuShiEngine(config=config, obsidian_vault=vault)
    await engine.__aenter__()
    engine._scenario = scenario

    history: list[dict] = []
    current_depth = depth
    show_think = think
    show_explain = explain
    searcher = WebSearcher()

    # ── 键盘绑定 ──
    bindings = KeyBindings()
    @bindings.add(Keys.ControlC)
    def _ctrl_c(event):
        event.app.exit(exception=KeyboardInterrupt)

    # ── 状态栏 ──
    def status_toolbar():
        tw = shutil.get_terminal_size().columns
        d_label = {1: "快速", 2: "标准", 3: "深度"}.get(current_depth, "标准")
        t_label = "完整推理" if show_think else "简洁"
        cur_scenario = getattr(engine, "_scenario", scenario)
        if tw < 50:
            return f"深度{d_label} | {t_label} | {len(history)}条 | /help"
        elif tw < 80:
            return f" 🧠 深度:{d_label} | {t_label} | 💬 {len(history)}条 | Ctrl+C 退出 | /help"
        return f" 🧠 深度:{d_label} | {t_label} | 💬 {len(history)}条 | 🛡️ {cur_scenario} | ↑↓ 浏览历史 · Tab 补全 · /help"

    # ── 补全 ──
    completion_words = [
        "/help", "/new", "/clear", "/exit", "/quit",
        "/think", "/depth 1", "/depth 2", "/depth 3",
        "/web", "/search", "/profile", "/card", "/note",
        "/dialectic 2 ", "/dialectic 3 ",
        "/council 2 ", "/council 3 ",
        "/history", "/personae", "/knowledge", "/scenario",
    ]
    # 中文描述 meta
    meta_dict = {
        "/help": "查看所有命令",
        "/new": "开始新一轮对话",
        "/clear": "清屏",
        "/exit": "退出",
        "/quit": "退出",
        "/think": "切换显示/隐藏推理过程",
        "/depth 1": "快速回答模式",
        "/depth 2": "标准深度回答",
        "/depth 3": "深度思考回答",
        "/web": "联网搜索",
        "/search": "搜索本地知识库",
        "/profile": "查看/编辑用户画像",
        "/card": "生成知识卡片",
        "/note": "添加笔记到 Obsidian",
        "/dialectic 2 ": "苏格拉底追问 (2轮)",
        "/dialectic 3 ": "苏格拉底追问 (3轮)",
        "/council 2 ": "多人格辩论 (2名哲人)",
        "/council 3 ": "多人格辩论 (3名哲人)",
        "/history": "查看对话历史",
        "/personae": "查看哲学人格",
        "/knowledge": "管理本地知识库",
        "/scenario": "切换场景",
    }
    completer = FuzzyCompleter(WordCompleter(completion_words, meta_dict=meta_dict))

    session_ps = PromptSession(
        key_bindings=bindings,
        history=FileHistory(HISTORY_FILE),
        bottom_toolbar=status_toolbar,
        completer=completer,
    )

    # 欢迎提示
    tw = shutil.get_terminal_size().columns
    if tw < 50:
        console.print("[dim]输入问题开始对话，或输入 / 查看命令[/dim]")
    else:
        hint_items = ["输入问题开始思辨", "输入 / 使用命令", "↑↓ 浏览历史"]
        console.print(f"[dim]{' · '.join(hint_items[:2]) + (' · ' + hint_items[2] if tw >= 60 else '')}[/dim]")
    console.print()

    try:
        while True:
            try:
                # 动态提示符 — 首次简洁提示，后续显示当前场景
                cur_sc = getattr(engine, "_scenario", scenario)
                if len(history) == 0:
                    user_input = await session_ps.prompt_async("\n求是 ")
                elif cur_sc != "general":
                    scene_emoji = {"career": "💼", "relationship": "💕", "management": "📊"}.get(cur_sc, "")
                    user_input = await session_ps.prompt_async(f"\n{scene_emoji} 你 ")
                else:
                    user_input = await session_ps.prompt_async("\n你 ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]👋 再见。思辨，然后行动。[/dim]")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # ── 斜杠命令 ──
            if user_input.startswith("/"):
                handled, should_exit, new_depth, new_think = await _handle_slash_command(
                    user_input, engine, sid, history,
                    current_depth, show_think, show_explain, scenario,
                    searcher, config, vault, session_ps,
                )
                if new_depth is not None:
                    current_depth = new_depth
                if new_think is not None:
                    show_think = new_think
                if should_exit:
                    break
                if handled:
                    continue

            # ── 正常对话 ──
            history.append({"role": "user", "content": user_input})
            if len(history) > 50:
                history = history[-50:]

            console.print()
            with console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
                result = await engine.process_with_result(sid, user_input, depth=current_depth)

            if show_explain:
                console.print(result.to_explain_text(user_input))
            elif show_think:
                console.print(Panel(
                    Markdown(result.full_text),
                    border_style=BRAND_PRIMARY, padding=(1, 2),
                    subtitle="[dim]求是思考[/dim]",
                ))
            else:
                console.print(Panel(
                    Markdown(result.public_text),
                    border_style=BRAND_SECONDARY, padding=(1, 2),
                    subtitle="[dim]求是回答[/dim]",
                ))
    finally:
        await engine.close()


async def _handle_slash_command(
    cmd: str, engine, sid, history, depth, think, explain, scenario,
    searcher, config, vault, session_ps,
) -> tuple[bool, bool, int | None, bool | None]:
    """处理斜杠命令。返回 (handled, should_exit, new_depth, new_think)"""
    c = cmd.strip().lower()
    new_depth: int | None = None
    new_think: bool | None = None

    # ── /help ──
    if c == "/help":
        tw = shutil.get_terminal_size().columns
        if tw < 50:
            console.print(f"[bold {BRAND_PRIMARY}]求是 — 哲学思辨助手[/bold {BRAND_PRIMARY}]")
            console.print("[bold]基础:[/bold] /help /new /clear /exit")
            console.print("[bold]思辨:[/bold] /dialectic N? /council 2|3? /think /depth N")
            console.print("[bold]工具:[/bold] /web? /profile /card /note /history /search /knowledge")
            console.print("[dim]?后参数可选 · 继续输入直接对话[/dim]")
        elif tw < 60:
            console.print(f"[bold {BRAND_PRIMARY}]求是 — 以哲学思辨为框架的 AI 思考伙伴[/bold {BRAND_PRIMARY}]")
            console.print("[bold]基础[/bold] /help /new /clear /exit /quit")
            console.print("[bold]思辨[/bold] /dialectic N? /council 2|3? /think /depth 1|2|3")
            console.print("[bold]工具[/bold] /web? /profile /card /note /history N[/full? /search? /knowledge /personae")
            console.print("[dim]输入 /help 命令名 查看具体用法[/dim]")
        else:
            console.print(HELP_TEXT)
        return True, False, None, None

    # ── /new ──
    if c == "/new":
        history.clear()
        console.print(f"[dim]🔄 新对话，历史已清空[/dim]")
        return True, False, None, None

    # ── /clear ──
    if c == "/clear":
        console.clear()
        console.print(_make_banner_terminal())
        return True, False, None, None

    # ── /exit /quit ──
    if c in ("/exit", "/quit"):
        return True, True, None, None

    # ── /think ──
    if c == "/think":
        new_think = not think
        console.print(f"[dim]{'✅ 显示完整推理' if new_think else '✅ 仅显示结论'}[/dim]")
        return True, False, None, new_think

    # ── /depth N ──
    if c.startswith("/depth"):
        parts = c.split()
        if len(parts) >= 2 and parts[1].isdigit():
            d = int(parts[1])
            if 1 <= d <= 3:
                new_depth = d
                console.print(f"[dim]🧠 深度 → {d} ({['快速','标准','深度'][d-1]})[/dim]")
                return True, False, new_depth, None
        console.print(f"[dim]用法: /depth 1|2|3 (当前: {depth})[/dim]")
        return True, False, None, None

    # ── /web <query> ──
    if c.startswith("/web "):
        query = cmd[5:].strip()
        if not query:
            console.print("[dim]用法: /web <搜索关键词>[/dim]")
            return True, False, None, None

        with console.status(LOADING_PHASES["searching"][0], spinner=LOADING_PHASES["searching"][1]):
            search_results = await searcher.search(query)
            context = searcher.format_context(search_results)

        if not search_results or len(search_results) == 0:
            console.print("[yellow]⚠ 未搜索到结果[/yellow]")
            return True, False, None, None

        # 自适应搜索结果
        tw = shutil.get_terminal_size().columns
        console.print()
        results_panel = []
        for i, r in enumerate(search_results, 1):
            title = r.get("title", "")
            body = r.get("body", "")[:100 if tw < 80 else 150]
            href = r.get("href", "")
            results_panel.append(f"[bold {BRAND_INFO}]{i}. {title}[/bold {BRAND_INFO}]")
            if body:
                results_panel.append(f"   [dim]{body}[/dim]")
            if href and tw >= 60:
                results_panel.append(f"   [link={href}]{href}[/link]")
            results_panel.append("")

        console.print(Panel(
            "\n".join(results_panel),
            title="[bold]搜索结果[/bold]",
            border_style=BRAND_INFO,
            padding=(1, 2),
        ))

        # 搜索+思辨
        combined_query = f"{query}\n\n以下是相关搜索结果：\n{context}\n\n请基于以上信息进行分析。"
        history.append({"role": "user", "content": combined_query})
        if len(history) > 50:
            history = history[-50:]

        with console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
            result = await engine.process_with_result(sid, combined_query, depth=depth)

        console.print(Panel(
            Markdown(result.public_text),
            title=f"[bold {BRAND_PRIMARY}]求是分析[/bold {BRAND_PRIMARY}]",
            border_style=BRAND_PRIMARY,
            padding=(1, 2),
        ))
        return True, False, None, None

    # ── /dialectic N <问题> ──
    if c.startswith("/dialectic"):
        parts = cmd.split(maxsplit=2)
        rounds = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 2
        question = parts[2] if len(parts) >= 3 else ""
        if not question:
            console.print("[dim]用法: /dialectic <轮数> <问题>[/dim]")
            console.print("[dim]例如: /dialectic 3 该不该辞职[/dim]")
            return True, False, None, None
        rounds = min(max(rounds, 1), 5)
        await _run_dialectic_tui(engine, sid, question, rounds, depth, session_ps)
        return True, False, None, None

    # ── /council N <问题> ──
    if c.startswith("/council"):
        parts = cmd.split(maxsplit=2)
        members = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 2
        question = parts[2] if len(parts) >= 3 else ""
        if not question:
            console.print("[dim]用法: /council <2|3> <问题>[/dim]")
            console.print("[dim]例如: /council 3 努力重要还是选择重要[/dim]")
            return True, False, None, None
        members = min(max(members, 2), 3)
        await _run_council_tui(engine, sid, question, members, depth, think)
        return True, False, None, None

    # ── /profile ──
    if c == "/profile":
        await _run_profile()
        return True, False, None, None

    # ── /card <keyword> ──
    if c.startswith("/card"):
        keyword = cmd[6:].strip() if len(cmd) > 5 else ""
        await _run_card(keyword)
        return True, False, None, None

    # ── /note <content> ──
    if c.startswith("/note "):
        content = cmd[6:].strip()
        if content:
            write_note(content)
            console.print(f"[green]✅ 笔记已保存[/green]")
        else:
            console.print("[dim]用法: /note <内容>[/dim]")
        return True, False, None, None

    # ── /knowledge <action> [--path PATH] ──
    if c.startswith("/knowledge"):
        parts = c.split(maxsplit=2)
        action = parts[1] if len(parts) >= 2 else ""
        if not action or action not in ("add", "list", "reload"):
            console.print(f"[bold {BRAND_PRIMARY}]知识库管理[/bold {BRAND_PRIMARY}]")
            console.print("  /knowledge list        列出已加载的知识")
            console.print("  /knowledge reload      重新加载知识库")
            console.print(f"[dim]  或使用 CLI: qiushi knowledge add --path <路径>[/dim]")
            return True, False, None, None

        from pathlib import Path as _Path
        if action == "list":
            if not USER_KNOWLEDGE_DIR.exists():
                console.print("[dim]用户知识库为空[/dim]")
            else:
                from rich.table import Table as _Table
                from rich import box as _box
                t = _Table(box=_box.SIMPLE, header_style=f"bold {BRAND_PRIMARY}")
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
                console.print(t)

        elif action == "reload":
            from .retriever import KnowledgeRetriever
            kr = KnowledgeRetriever()
            kr.reload()
            console.print("[green]✅ 知识库已重新加载[/green]")

        elif action == "add":
            # /knowledge add 需要路径参数，通过 CLI 更方便
            console.print(f"[dim]请使用命令行: qiushi knowledge add --path <路径>[/dim]")

        return True, False, None, None

    # ── /history [N] [full|all] ──
    if c.startswith("/history"):
        parts = c.split()
        show_full = "full" in parts or "all" in parts
        n_parts = [p for p in parts[1:] if p.isdigit()]
        n = int(n_parts[0]) if n_parts else 10
        n = min(max(n, 1), 50)
        if not history:
            console.print("[dim]暂无对话历史[/dim]")
            return True, False, None, None
        recent = history[-n:]
        tw = shutil.get_terminal_size().columns
        if show_full:
            # 完整模式 — 每条内容不截断
            console.print(f"\n[bold {BRAND_PRIMARY}]══ 最近 {len(recent)} 条对话（完整）══[/bold {BRAND_PRIMARY}]\n")
            for i, entry in enumerate(recent, 1):
                role = entry.get("role", "user")
                content = entry.get("content", "")
                icon = "👤" if role == "user" else "🧠"
                role_name = "你" if role == "user" else "求是"
                console.print(Panel(
                    content,
                    title=f"[bold]{icon} {role_name} (#{i})[/bold]",
                    border_style=BRAND_PRIMARY if role == "user" else BRAND_SECONDARY,
                    padding=(1, 2),
                ))
                console.print()
        else:
            # 紧凑模式 — 预览
            max_chars = 60 if tw < 60 else 120 if tw < 80 else 200
            console.print(f"[bold]最近 {len(recent)} 条对话：[/bold]")
            for i, entry in enumerate(recent, 1):
                role = entry.get("role", "user")
                content = entry.get("content", "")
                icon = "👤" if role == "user" else "🧠"
                if len(content) > max_chars:
                    content = content[:max_chars] + f" [dim]...（共{len(entry.get('content',''))}字）[/dim]"
                console.print(f"  {icon} {content}")
            if tw >= 50:
                console.print(f"[dim]提示: /history {n} full 查看完整内容[/dim]")
        return True, False, None, None

    # ── /version ──
    if c == "/version":
        from . import __version__
        console.print(f"[dim]求是 v{__version__}[/dim]")
        return True, False, None, None

    # ── /search <关键词> ──
    if c.startswith("/search "):
        query = cmd[8:].strip()
        if not query:
            console.print("[dim]用法: /search <关键词> — 在本地知识库中搜索[/dim]")
            return True, False, None, None
        with console.status(LOADING_PHASES["searching"][0], spinner=LOADING_PHASES["searching"][1]):
            from .retriever import KnowledgeRetriever
            kr = KnowledgeRetriever()
            results = kr.search(query, top_k=5)
        if not results:
            msg = '[yellow]⚠ 本地知识库中未找到 "{}" 相关内容[/yellow]'.format(query)
            console.print(msg)
            console.print("[dim]提示: 试试 /web <关键词> 搜索网络，或 /knowledge add --path <路径> 添加本地知识[/dim]")
            return True, False, None, None
        tw = shutil.get_terminal_size().columns
        console.print()
        results_lines = []
        for i, r in enumerate(results, 1):
            content_preview = r.get("content", "")[:150 if tw < 80 else 200]
            source = r.get("source", "")
            score = r.get("score", 0)
            results_lines.append(f"[bold {BRAND_INFO}]{i}. {content_preview}[/bold {BRAND_INFO}]")
            if source:
                results_lines.append(f"   [dim]📄 {source} (相关度: {score:.0%})[/dim]")
            results_lines.append("")
        console.print(Panel(
            "\n".join(results_lines),
            title=f"[bold]知识库搜索: {query}[/bold]",
            border_style=BRAND_INFO,
            padding=(1, 2),
        ))
        return True, False, None, None

    if c == "/search":
        console.print("[dim]用法: /search <关键词> — 在本地知识库中搜索[/dim]")
        return True, False, None, None

    # ── /personae ──
    if c.startswith("/personae"):
        parts = cmd.split(maxsplit=1)
        subaction = parts[1].strip() if len(parts) >= 2 else ""
        if subaction == "detail":
            console.print(f"[bold {BRAND_PRIMARY}]哲学人格列表[/bold {BRAND_PRIMARY}]")
            for name, style in PERSONA_STYLE.items():
                desc_map = {
                    "斯多葛": "关注可控与不可控的界限，倡导理性、克制和内在平静",
                    "辩证唯物": "关注矛盾分析、实践检验、结构性视角",
                    "存在主义": "关注自由选择、个体责任、意义的自我创造",
                    "求是": "综合各流派精华，实事求是分析问题",
                    "苏格拉底": "通过追问揭示问题本质，不预设答案",
                }
                console.print(f"  {style['emoji']} [bold {style['color']}]{name}[/bold {style['color']}] — [dim]{desc_map.get(name, '')}[/dim]")
            return True, False, None, None
        if not subaction:
            console.print(f"[bold {BRAND_PRIMARY}]可用哲学人格[/bold {BRAND_PRIMARY}]")
            tw = shutil.get_terminal_size().columns
            names = list(PERSONA_STYLE.keys())
            if tw < 50:
                console.print("  " + " · ".join(names))
            else:
                for name in names:
                    style = PERSONA_STYLE[name]
                    console.print(f"  {style['emoji']} [{style['color']}]{name}[/{style['color']}]")
            console.print("[dim]输入 /personae detail 查看详细介绍[/dim]")
            return True, False, None, None

    # ── /scenario <name> ──
    if c.startswith("/scenario"):
        parts = c.split(maxsplit=1)
        new_scenario = parts[1].strip() if len(parts) >= 2 else ""
        valid_scenarios = ["general", "career", "relationship", "management"]
        if not new_scenario:
            current_style = {"general": "🌐 通用", "career": "💼 职业", "relationship": "💕 关系", "management": "📊 管理"}
            console.print(f"[bold {BRAND_PRIMARY}]场景切换[/bold {BRAND_PRIMARY}]")
            for s in valid_scenarios:
                marker = "►" if s == scenario else " "
                color = BRAND_INFO if s == scenario else "dim"
                console.print(f"  {marker} [{color}]{current_style.get(s, s)} ({s})[/]")
            console.print(f"[dim]当前: {scenario} | 用法: /scenario <场景名>[/dim]")
            return True, False, None, None
        if new_scenario in valid_scenarios:
            engine._scenario = new_scenario
            name_map = {"general": "🌐 通用", "career": "💼 职业", "relationship": "💕 关系", "management": "📊 管理"}
            console.print(f"[green]✅ 场景已切换至: {name_map.get(new_scenario, new_scenario)}[/green]")
            return True, False, None, None
        console.print(f"[dim]无效场景。可选: {', '.join(valid_scenarios)}[/dim]")
        return True, False, None, None

    # ── 未知 ──
    if c.startswith("/"):
        console.print(f"[dim]未知命令: {c} (输入 /help 查看帮助)[/dim]")
        return True, False, None, None

    return False, False, None, None


# ═══════════════════════════════════════════════════════════════════
#  ask 命令（带 TUI）
# ═══════════════════════════════════════════════════════════════════

@app.command()
def ask(
    message: str | None = typer.Argument(None, help="问题文本"),
    input_file: str | None = typer.Option(None, "--input", "-i", help="从文件读取问题"),
    output_file: str | None = typer.Option(None, "--output", "-o", help="将回答写入文件"),
    session: str | None = typer.Option(None, "--session", "-s", help="会话 ID"),
    depth: int = typer.Option(2, "--depth", "-d", help="分析深度 1-3"),
    think: bool = typer.Option(False, "--think", "-t", help="显示完整推理过程"),
    explain: bool = typer.Option(False, "--explain", "-e", help="展示内部决策信息"),
    dialectic: int | None = typer.Option(None, "--dialectic", help="苏格拉底追问轮数 (1-5)"),
    council: int | None = typer.Option(None, "--council", help="多哲学人格辩论 (2-3)"),
    web: str | None = typer.Option(None, "--web", "-w", help="搜索最新资讯后再分析"),
    output_format: str = typer.Option("text", "--format", "-f", help="text / json"),
    scenario: str = typer.Option("general", "--scenario", "-c", help="场景"),
):
    """单次问答（带 TUI 效果）"""
    _confirm_api()

    if input_file:
        question = Path(input_file).read_text(encoding="utf-8").strip()
    elif message:
        question = message
    else:
        raise typer.BadParameter("请提供问题文本或使用 --input 指定文件")

    config = QiushiConfig.load()
    vault = config.obsidian_vault or _detect_obsidian_vault()
    sid = session or str(uuid.uuid4())[:8]

    asyncio.run(
        _ask_tui(question, sid, config, vault, depth, think, explain,
                 dialectic, council, web, output_file, output_format, scenario)
    )


async def _ask_tui(
    question: str, sid: str, config, vault,
    depth: int, think: bool, explain: bool,
    dialectic: int | None, council: int | None,
    web: str | None, output_file: str | None,
    output_format: str, scenario: str,
):
    engine = QiuShiEngine(config=config, obsidian_vault=vault)
    async with engine:
        engine._scenario = scenario
        searcher = WebSearcher()

        # ── 先搜索（如有） ──
        if web:
            with console.status(LOADING_PHASES["searching"][0], spinner=LOADING_PHASES["searching"][1]):
                ctx = await searcher.search_and_format(web)
            if ctx:
                question = f"{question}\n\n{ctx}"
            console.print(f"[dim]✅ 已搜索: {web}[/dim]")

        # ── 苏格拉底追问链 ──
        if dialectic:
            rounds = min(max(dialectic, 1), 5)
            session_ps = PromptSession(history=FileHistory(HISTORY_FILE))
            await _run_dialectic_tui(engine, sid, question, rounds, depth, session_ps)

        # ── 多哲学人格辩论 ──
        elif council:
            members = min(max(council, 2), 3)
            await _run_council_tui(engine, sid, question, members, depth, think)

        # ── 普通问答 ──
        else:
            with console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
                result = await engine.process_with_result(sid, question, depth=depth)

            if output_format == "json":
                output = json.dumps(result.to_json(question, show_think=think), ensure_ascii=False, indent=2)
            elif explain:
                output = result.to_explain_text(question)
            elif think:
                output = result.full_text
            else:
                output = result.public_text

            if output_file:
                Path(output_file).write_text(output, encoding="utf-8")
                console.print(f"[green]✅ 回答已写入: {output_file}[/green]")
            else:
                console.print()
                if explain:
                    console.print(output)
                else:
                    console.print(Panel(
                        Markdown(output) if not think else output,
                        border_style=BRAND_PRIMARY if think else BRAND_SECONDARY,
                        padding=(1, 2),
                        subtitle="[dim]求是回答[/dim]" if not think else None,
                    ))
                console.print()


# ═══════════════════════════════════════════════════════════════════
#  苏格拉底追问链（TUI 版）
# ═══════════════════════════════════════════════════════════════════

async def _run_dialectic_tui(
    engine: QiuShiEngine, sid: str, question: str,
    rounds: int, depth: int,
    session_ps: PromptSession,
):
    """交互式苏格拉底追问链，使用 prompt_toolkit 而非 typer.prompt"""
    session = DialecticSession(max_rounds=rounds)
    rounds_data = []

    console.print(f"\n[bold {BRAND_PRIMARY}]══ 苏格拉底追问链（共{rounds}轮）══[/bold {BRAND_PRIMARY}]\n")

    for i in range(rounds):
        if i == 0:
            # 第一轮
            with console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
                result = await engine.process_with_result(sid, question, depth=depth)
                session.results.append(result)
                session.history.append({"role": "user", "content": question})
                session.history.append({"role": "assistant", "content": result.public_text})
                session.round = 1

            # 生成追问
            follow_up = await session._generate_follow_up(engine, sid, question)

            render_dialectic_round(1, rounds, result.public_text, follow_up)

            if rounds == 1:
                rounds_data.append({"analysis": result.public_text, "follow_up": follow_up})
                break

            rounds_data.append({"analysis": result.public_text, "follow_up": follow_up})

            try:
                user_response = await session_ps.prompt_async("\n你的回答 > ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]追问已结束，正在整理已有思辨结果...[/dim]")
                break

            session.history.append({"role": "user", "content": user_response})
            session.round = 2

        else:
            # 第 2+ 轮
            context = f"原始问题：{question}\n\n我们已经讨论到第{i+1}轮。用户的最新回应：{user_response}"
            with console.status(LOADING_PHASES["thinking"][0], spinner=LOADING_PHASES["thinking"][1]):
                result = await engine.process_with_result(sid, context, history=session.history[:-1], depth=depth)
                session.results.append(result)
                session.history.append({"role": "assistant", "content": result.public_text})

            if session.round >= rounds:
                render_dialectic_round(i + 1, rounds, result.public_text, None)
                rounds_data.append({"analysis": result.public_text, "follow_up": None})
                break

            follow_up = await session._generate_follow_up(engine, sid, question)
            render_dialectic_round(i + 1, rounds, result.public_text, follow_up)
            rounds_data.append({"analysis": result.public_text, "follow_up": follow_up})

            try:
                user_response = await session_ps.prompt_async("\n你的回答 > ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]追问已结束，正在整理已有思辨结果...[/dim]")
                break

            session.history.append({"role": "user", "content": user_response})
            session.round += 1

    # 辩证总结
    synthesis = session._synthesize()
    render_dialectic_summary(synthesis)


# ═══════════════════════════════════════════════════════════════════
#  多哲学人格辩论（TUI 版）
# ═══════════════════════════════════════════════════════════════════

async def _run_council_tui(
    engine: QiuShiEngine, sid: str, question: str,
    members: int, depth: int, think: bool,
):
    """多哲学人格辩论，带 TUI 动画"""
    councils = {
        2: [
            ("斯多葛", "你是一个斯多葛主义者。关注可控与不可控的界限，倡导理性、克制和内在平静。"),
            ("辩证唯物", "你是一个辩证唯物主义者。关注矛盾分析、实践检验、结构性视角。"),
        ],
        3: [
            ("斯多葛", "你是一个斯多葛主义者。关注可控与不可控的界限，倡导理性、克制和内在平静。"),
            ("辩证唯物", "你是一个辩证唯物主义者。关注矛盾分析、实践检验、结构性视角。"),
            ("存在主义", "你是一个存在主义者。关注自由选择、个体责任、意义的自我创造。"),
        ],
    }

    pairs = councils.get(members, councils[2])
    console.print(f"\n[bold {BRAND_PRIMARY}]══ 多哲学人格辩论（{members}人）══[/bold {BRAND_PRIMARY}]\n")

    async def _call_councillor(name: str, persona: str) -> dict:
        pb = PromptBuilder()
        system_prompt = persona + "\n\n" + pb.get_system_prompt(depth=depth)
        msgs = [{"role": "user", "content": question}]
        try:
            reply = await engine._llm.chat(msgs, system=system_prompt)
            reply = engine._sanitize(reply)
            return {"name": name, "reply": reply}
        except Exception as e:
            return {"name": name, "reply": None, "error": str(e)}

    with console.status(LOADING_PHASES["debating"][0], spinner=LOADING_PHASES["debating"][1]):
        council_results = await asyncio.gather(*[
            _call_councillor(name, persona) for name, persona in pairs
        ])

    # 共识与分歧
    valid = [r for r in council_results if not r.get("error")]
    synthesis = ""
    if len(valid) >= 2:
        with console.status(LOADING_PHASES["summarizing"][0], spinner=LOADING_PHASES["summarizing"][1]):
            views = "\n".join([f"【{r['name']}】{r['reply'][:300]}" for r in valid])
            summary_prompt = (
                f"以下是对同一问题的不同哲学视角的回答。请找出它们的共识点和分歧点：\n\n{views}"
            )
            try:
                synthesis = await engine._llm.chat(
                    [{"role": "user", "content": summary_prompt}],
                    system="你是一个公正的分析师。列出共识点和分歧点，不要偏向任何一方。",
                    temperature=0.3,
                )
                synthesis = synthesis.strip()
            except LLMError:
                pass

    # TUI 动画展示
    render_council_debate(council_results, synthesis)
    console.print()


# ═══════════════════════════════════════════════════════════════════
#  其他命令（保留原有功能，TUI 风格输出）
# ═══════════════════════════════════════════════════════════════════

@app.command()
def card(keyword: str = typer.Argument("", help="可选关键词")):
    """生成哲学思辨卡片"""
    result = generate_card(keyword)
    console.print()
    console.print(Panel(Markdown(result), border_style=BRAND_PRIMARY, padding=(1, 2), title="[bold]思辨卡片[/bold]"))
    console.print()


@app.command()
def note(
    content: str = typer.Argument("", help="笔记内容"),
    tag: str | None = typer.Option(None, "--tag", "-t", help="标签"),
    type: str = typer.Option("note", "--type", help="note / decision"),
    done: bool = typer.Option(False, "--done", "-d", help="标记为已执行"),
    list_only: bool = typer.Option(False, "--list", "-l", help="列出笔记"),
):
    """记录笔记或标记决策已执行"""
    if list_only:
        entries = db_list_entries("note" if type == "note" else None)
        if not entries:
            console.print("[dim]还没有笔记[/dim]")
            return
        t = Table(box=box.SIMPLE, header_style=f"bold {BRAND_PRIMARY}")
        t.add_column("类型")
        t.add_column("内容")
        t.add_column("时间")
        for e in entries[:20]:
            preview = e.get("content", "")[:60].replace("\n", " ")
            t.add_row(
                f"[{BRAND_INFO}]{e['type']}[/]",
                preview,
                str(e.get("created_at", ""))[:10],
            )
        console.print(t)
        return

    if not content and not done:
        console.print("[dim]请提供笔记内容，或使用 --done + 关键词 标记已执行[/dim]")
        raise typer.Exit(1)

    uid = get_or_create_user_id()
    if done:
        result = mark_decision_done(uid, content)
        if result:
            update_user_decision(uid, content)
            console.print(f"[green]✅ 已标记为已执行[/green]")
        else:
            console.print("[yellow]未找到匹配的决策记录[/yellow]")
        return

    if type == "decision":
        upsert_decision(uid, content)
        console.print(f"[green]✅ 决策已记录[/green]")
    else:
        tags = [tag] if tag else None
        write_note(content, tags=tags)
        console.print(f"[green]✅ 笔记已保存[/green]")


async def _run_profile():
    """查看思维画像（自适应终端宽度）"""
    uid = get_or_create_user_id()
    summary = profile_summary(uid)
    tw = shutil.get_terminal_size().columns

    t = Table(box=box.ROUNDED, header_style=f"bold {BRAND_PRIMARY}")
    t.add_column("维度")
    t.add_column("值")
    t.add_row("对话次数", str(summary["conversation_count"]))
    t.add_row("严厉指数", f"{summary['strictness']:.0%}")
    t.add_row("决策执行率", f"{summary['execution_rate']:.0%}")
    console.print()
    console.print(Panel(t, title="[bold]思维画像[/bold]", border_style=BRAND_PRIMARY, padding=(1, 1)))

    contradictions = summary.get("contradictions", [])
    if contradictions:
        ct = Table(box=box.SIMPLE, header_style=f"bold {BRAND_ACCENT}")
        ct.add_column("矛盾类型")
        ct.add_column("次数")
        ct.add_column("状态")
        if tw >= 80:
            ct.add_column("最近建议")
        for c in contradictions:
            shift = "✓ 已转变" if c.get("shift") else "→ 持续中"
            suggestion = (c.get("last_suggestion") or "")[:40]
            row = [c["type"], str(c.get("count", 1)), shift]
            if tw >= 80:
                row.append(suggestion)
            ct.add_row(*row)
        console.print(Panel(ct, title="[bold]矛盾演变[/bold]", border_style=BRAND_ACCENT, padding=(1, 1)))
    console.print()


@app.command()
def profile():
    """查看你的思维画像"""
    asyncio.run(_run_profile())


@app.command()
def knowledge(
    action: str | None = typer.Argument(None, help="add / list / reload"),
    path: str | None = typer.Option(None, "--path", "-p", help="文件或目录路径"),
    tag: str | None = typer.Option(None, "--tag", "-t", help="标签"),
):
    """管理用户自定义知识库"""
    if not action or action not in ("add", "list", "reload"):
        console.print(f"\n[bold {BRAND_PRIMARY}]📚 知识库管理[/bold {BRAND_PRIMARY}]\n")
        console.print("[bold]用法:[/bold] qiushi knowledge <动作>")
        console.print()
        console.print("  [bold]add[/bold]    添加知识文件")
        console.print("            qiushi knowledge add --path <文件或目录>")
        console.print()
        console.print("  [bold]list[/bold]   列出已加载的知识")
        console.print()
        console.print("  [bold]reload[/bold] 重新加载知识库")
        console.print()
        console.print("[dim]提示: 在 TUI 中也可用 /knowledge list 和 /knowledge reload[/dim]")
        return

    if action == "add":
        if not path:
            console.print("[red]请指定 --path[/red]")
            raise typer.Exit(1)
        src = Path(path)
        if not src.exists():
            console.print(f"[red]文件不存在: {path}[/red]")
            raise typer.Exit(1)
        dest_dir = USER_KNOWLEDGE_DIR / "user"
        dest_dir.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            dest = dest_dir / src.name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            console.print(f"[green]✅ 已添加: {src.name}[/green]")
        elif src.is_dir():
            count = 0
            for f in src.rglob("*.md"):
                if f.is_file():
                    (dest_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                    count += 1
            console.print(f"[green]✅ 已添加 {count} 个文件[/green]")
        if tag:
            tag_path = dest_dir / ".tags"
            existing = json.loads(tag_path.read_text(encoding="utf-8")) if tag_path.exists() else {}
            for f in dest_dir.iterdir():
                if f.suffix == ".md":
                    existing.setdefault(f.stem, []).append(tag)
            tag_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print("[dim]知识库已更新，下次提问时自动生效[/dim]")

    elif action == "list":
        if not USER_KNOWLEDGE_DIR.exists():
            console.print("[dim]用户知识库为空[/dim]")
            return
        t = Table(box=box.SIMPLE, header_style=f"bold {BRAND_PRIMARY}")
        t.add_column("目录/文件")
        t.add_column("段落数")
        total = 0
        for subdir in sorted(USER_KNOWLEDGE_DIR.iterdir()):
            if subdir.is_dir():
                files = list(subdir.glob("*.md"))
                if files:
                    for f in files:
                        paras = len(f.read_text(encoding="utf-8").split("\n\n"))
                        total += paras
                        t.add_row(f"  {subdir.name}/{f.name}", str(paras))
        t.add_row(f"[bold]合计[/bold]", str(total))
        console.print(t)

    elif action == "reload":
        from .retriever import KnowledgeRetriever
        kr = KnowledgeRetriever()
        kr.reload()
        console.print("[green]✅ 知识库已重新加载[/green]")

    else:
        console.print("[dim]支持的动作: add / list / reload[/dim]")


@app.command()
def adapter(
    action: str = typer.Argument(..., help="add / list / remove"),
    type: str = typer.Option("dir", "--type", "-t", help="dir / obsidian"),
    path: str = typer.Option("", "--path", "-p", help="本地路径"),
    label: str = typer.Option("", "--label", "-l", help="标签"),
    name: str = typer.Option("", "--name", "-n", help="要移除的适配器名"),
):
    """管理外部知识源适配器"""
    if action == "add":
        if not path:
            console.print("[red]请指定 --path[/red]")
            raise typer.Exit(1)
        adapters = load_adapters()
        if type == "dir":
            adapters.append(DirectoryAdapter(path, label=label))
        elif type == "obsidian":
            adapters.append(ObsidianAdapter(path))
        else:
            console.print(f"[red]不支持的适配器类型: {type}[/red]")
            raise typer.Exit(1)
        save_adapters(adapters)
        console.print(f"[green]✅ 已添加 {type} 适配器: {path}[/green]")

    elif action == "list":
        adapters = load_adapters()
        if not adapters:
            console.print("[dim]没有配置的外部知识源[/dim]")
            return
        for a in adapters:
            files = a.list_files()
            console.print(f"  {a.name()}（{len(files)} 个文件）")
            for f in files[:5]:
                console.print(f"    {f.name}")
            if len(files) > 5:
                console.print(f"    ... 还有 {len(files) - 5} 个文件")

    elif action == "remove":
        if not name:
            console.print("[red]请指定 --name[/red]")
            raise typer.Exit(1)
        adapters = load_adapters()
        before = len(adapters)
        adapters = [a for a in adapters if a.name() != name]
        save_adapters(adapters)
        console.print(f"[green]已移除 {before - len(adapters)} 个适配器[/green]")

    else:
        console.print("[dim]支持的动作: add / list / remove[/dim]")


@app.command()
def session(
    action: str = typer.Argument(..., help="list / delete"),
    id: str | None = typer.Option(None, "--id", help="会话ID"),
):
    """管理辩证对话会话"""
    if action == "list":
        sessions = DialecticSession.list_sessions()
        if not sessions:
            console.print("[dim]没有保存的会话[/dim]")
            return
        t = Table(box=box.SIMPLE, header_style=f"bold {BRAND_PRIMARY}")
        t.add_column("Session ID")
        t.add_column("问题")
        t.add_column("轮数")
        for s in sessions:
            t.add_row(s["id"], s["question"][:50], f"{s['round']}/{s['max_rounds']}")
        console.print(t)
    elif action == "delete":
        if not id:
            console.print("[red]请指定 --id[/red]")
            raise typer.Exit(1)
        DialecticSession.delete(id)
        console.print(f"[green]已删除会话: {id}[/green]")
    else:
        console.print("[dim]支持的动作: list / delete[/dim]")


@app.command()
def feedback(
    good: bool = typer.Option(False, "--good", help="正面反馈"),
    bad: bool = typer.Option(False, "--bad", help="负面反馈"),
    session: str | None = typer.Option(None, "--session", "-s"),
):
    """反馈"""
    if not good and not bad:
        console.print("[dim]请提供 --good 或 --bad[/dim]")
        raise typer.Exit(1)
    from .db import save_feedback as db_feedback
    db_feedback("good" if good else "bad", session or "unknown")
    console.print("[green]✅ 感谢反馈！[/green]")


@app.command()
def server(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8765, "--port", "-p", help="监听端口"),
):
    """启动 HTTP API 服务器"""
    from .server import run_server
    run_server(host=host, port=port)


@app.command()
def init():
    """交互式初始化配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        overwrite = typer.prompt("配置已存在，是否覆盖？(y/N)", default="n")
        if overwrite.lower() != "y":
            typer.echo("取消配置。")
            return

    config = QiushiConfig()
    typer.echo("\n=== 求是初始化向导 ===\n")
    typer.echo("选择 LLM 提供者：")
    typer.echo("  1) DeepSeek（推荐）")
    typer.echo("  2) OpenAI")
    typer.echo("  3) Anthropic Claude")
    typer.echo("  4) Ollama（本地免费）")
    typer.echo("  5) 其他 (OpenRouter)")

    provider_choice = typer.prompt("请选择 (1-5)", default="1")
    provider_map = {"1": "deepseek", "2": "openai", "3": "anthropic", "4": "ollama", "5": "openrouter"}
    config.llm.provider = provider_map.get(provider_choice, "deepseek")

    if config.llm.provider == "ollama":
        import shutil
        if shutil.which("ollama"):
            model = typer.prompt("模型名", default="llama3.2")
            if model:
                config.llm.model = model
        else:
            typer.echo("❌ 未检测到 Ollama")
            config.llm.provider = "deepseek"

    if config.llm.provider in ("deepseek", "openai", "anthropic", "openrouter"):
        api_key = typer.prompt("API Key (留空使用环境变量)", default="")
        if api_key:
            config.llm.api_key = api_key

    if not config.llm.provider == "ollama":
        default_models = {
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
            "openrouter": "openai/gpt-4o-mini",
        }
        default_model = default_models.get(config.llm.provider, "deepseek-chat")
        model = typer.prompt("模型名", default=default_model)
        if model:
            config.llm.model = model

    vault = _detect_obsidian_vault()
    if vault:
        config.obsidian_vault = vault

    config.save()
    typer.echo(f"\n✅ 配置已保存到 {CONFIG_PATH}")
    console.print(_make_banner_terminal())


if __name__ == "__main__":
    app()