"""求是 (QiuShi) — 以哲学思辨为框架的 AI 思考伙伴"""

__version__ = "0.3.0"
__all__ = [
    "QiuShiEngine",
    "QiushiConfig",
    "LLMConfig",
    "LLMError",
    "CouncilResult",
    "run_council",
]

from .engine import QiuShiEngine
from .config import QiushiConfig, LLMConfig
from .llm import LLMError
from .council import CouncilResult, run_council
