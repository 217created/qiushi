"""求是 TUI — 漂亮终端界面"""
from .constants import *
from .dialectic_renderer import render_dialectic_round, render_dialectic_summary, render_dialectic_full, prompt_user
from .council_renderer import render_council_debate as render_council, render_council_summary
from .searcher import WebSearcher
