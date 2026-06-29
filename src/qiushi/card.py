"""思辨卡片生成器"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .retriever import KnowledgeRetriever


def generate_card(keyword: str = "") -> str:
    """基于知识库生成一张思辨卡片"""
    import asyncio
    kr = KnowledgeRetriever()

    if keyword:
        results = asyncio.run(kr.retrieve(keyword, top_k=3))
    else:
        kr._ensure_loaded()
        results = random.sample(kr.documents, min(3, len(kr.documents)))

    if not results:
        return "没有找到相关内容。"

    # 从检索结果中抽取素材
    main = results[0]
    title = main.get("title", "思辨卡片")
    content = main.get("content", "")[:200]

    # 构建卡片（纯文本，边框由 cli.py 的 Panel 处理）
    lines = [
        f"**{title}**",
        "",
        f"> {content}",
        "",
        f"💭 {_generate_reflection(title, keyword)}",
    ]

    _append_to_library(title, content)

    return "\n".join(lines)


def _generate_reflection(title: str, keyword: str) -> str:
    """生成反问句"""
    reflections = [
        f"你有没有经历过类似的情况？",
        f"这个道理在你的生活中成立吗？",
        f"如果用这个观点来看你现在的困境，会不一样吗？",
        f"你有没有相反的经验可以挑战这个观点？",
        f"这句话对你来说意味着什么？",
    ]
    return random.choice(reflections)


def _append_to_library(title: str, content: str):
    """追加到本地卡片库"""
    path = Path.home() / ".qiushi" / "cards.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = f"- 摘自《{title}》— {content[:100]}…\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
