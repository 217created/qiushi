"""求是 TUI 常量 — 品牌色、欢迎页、Agent 身份标识"""

from __future__ import annotations

# ── 品牌色 ───────────────────────────────────────────────────────
BRAND_PRIMARY = "#7C3AED"   # 靛紫 — 哲学/思辨感
BRAND_SECONDARY = "#00D4AA"  # 青绿 — 自然/清晰
BRAND_ACCENT = "#F59E0B"    # 琥珀 — 洞察/亮点
BRAND_ERROR = "#EF4444"     # 红
BRAND_SUCCESS = "#10B981"   # 绿
BRAND_INFO = "#3B82F6"     # 蓝

# ── 身份标识（哲学人格） ─────────────────────────────────────────
PERSONA_STYLE = {
    "斯多葛":     {"color": "#3B82F6", "emoji": "🛡️",  "short": "斯多葛"},
    "辩证唯物":   {"color": "#EF4444", "emoji": "⚔️",   "short": "辩证唯物"},
    "存在主义":   {"color": "#F59E0B", "emoji": "🔥",   "short": "存在主义"},
    "求是":       {"color": "#7C3AED", "emoji": "🧠",   "short": "求是"},
    "苏格拉底":   {"color": "#00D4AA", "emoji": "❓",   "short": "苏格拉底"},
}

def get_persona_style(name: str) -> dict:
    return PERSONA_STYLE.get(name, {"color": "#888888", "emoji": "🤖", "short": name})

# ── 欢迎 Banner ─────────────────────────────────────────────────
# 使用 pyfiglet 生成: python3 -m pyfiglet "QIUSHI" -f slant -w 80
BANNER_ASCII = r"""
    ____    ______  _______ __  ______
   / __ \  /  _/ / / / ___// / / /  _/
  / / / /  / // / / /\__ \/ /_/ // /
 / /_/ / _/ // /_/ /___/ / __  // /
 \___\_\/___/\____//____/_/ /_/___/
"""

WELCOME_BANNER = f"""[bold {BRAND_PRIMARY}]{BANNER_ASCII}[/bold {BRAND_PRIMARY}]
[dim]  以哲学思辨为框架的 AI 思考伙伴  |  /help 查看命令[/dim]"""

# ── 帮助文本 ─────────────────────────────────────────────────────
HELP_TEXT = f"""
[bold {BRAND_PRIMARY}]求是 CLI — 哲学思辨助手[/bold {BRAND_PRIMARY}]

[bold]基础命令:[/bold]
  /help            显示此帮助
  /new             新对话
  /clear           清屏
  /exit /quit      退出

[bold]思辨模式:[/bold]
  /dialectic <N> <问题>  苏格拉底追问链（N=1-5轮）
  /council <2|3> <问题>  多哲学人格辩论
  /think             切换是否显示完整推理过程
  /depth <1|2|3>    设置分析深度

[bold]搜索工具:[/bold]
  /web <关键词>       搜索最新资讯并纳入思辨分析

[bold]实用工具:[/bold]
  /profile           查看你的思维画像
  /card <关键词>      生成哲学思辨卡片
  /note <内容>       记录笔记
  /history [N]       查看最近N条对话

[dim]提示: 输入 /help <命令> 查看具体用法[/dim]
"""

# ── 进度/阶段文案 ───────────────────────────────────────────────
LOADING_PHASES = {
    "thinking":    ("[bold #7C3AED]🧠 思辨中...[/bold #7C3AED]", "dots"),
    "searching":   ("[bold #3B82F6]🔍 搜索中...[/bold #3B82F6]", "earth"),
    "debating":    ("[bold #F59E0B]⚡ 辩论中...[/bold #F59E0B]", "bounce"),
    "summarizing": ("[bold #00D4AA]📝 总结中...[/bold #00D4AA]", "material"),
    "loading":     ("[bold #7C3AED]⏳ 加载中...[/bold #7C3AED]", "dots"),
}
