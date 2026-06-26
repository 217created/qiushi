"""Council — 多哲学人格辩论核心逻辑（纯逻辑层，无渲染）"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from .engine import QiuShiEngine


@dataclass
class CouncilResult:
    """存储多哲学人格辩论的完整结果"""

    council_results: list[dict] = field(default_factory=list)
    """每个 councillor 的输出，每项包含 name, reply, error"""
    synthesis: str = ""
    """共识与分歧总结"""
    question: str = ""
    """原始问题"""
    members: int = 0
    """参与人数"""
    personae: list[dict] = field(default_factory=list)
    """使用的人格列表，每项包含 name, persona"""


async def run_council(
    engine: QiuShiEngine,
    question: str,
    personae: list[tuple[str, str]],
    depth: int = 2,
) -> CouncilResult:
    """运行多哲学人格辩论，返回纯结果（无渲染副作用）。

    Args:
        engine: QiuShiEngine 实例
        question: 辩论问题
        personae: [(name, persona_prompt), ...] — 外部可注入任意人格
        depth: 思辨深度

    Returns:
        CouncilResult 包含每位 councillor 的输出和共识分歧总结
    """

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

    council_results = await asyncio.gather(*[
        _call_councillor(name, persona) for name, persona in personae
    ])

    # 共识与分歧总结
    valid = [r for r in council_results if not r.get("error")]
    synthesis = ""
    if len(valid) >= 2:
        views = "\n\n".join([f"【{r['name']}】的观点：\n{r['reply']}" for r in valid])
        summary_prompt = (
            f"以下是同一问题的不同哲学视角的完整回答。请做一份结构化的分析总结：\n\n"
            f"{views}\n\n"
            f"请按以下结构输出：\n"
            f"## 各家观点\n"
            f"对每个流派用一段话概括其核心主张和论证路径。\n\n"
            f"## 分歧点\n"
            f"各流派之间在哪里产生根本对立，为什么。\n\n"
            f"## 逻辑链条\n"
            f"每家是如何从前提推导到结论的（因果链/类比/归谬等）。\n\n"
            f"## 未尽之处\n"
            f"有哪些被忽略但关键的问题没有被触及。"
        )
        try:
            synthesis = await engine._llm.chat(
                [{"role": "user", "content": summary_prompt}],
                system="你是一个公正的分析师。列出共识点和分歧点，不要偏向任何一方。",
                temperature=0.3,
            )
            synthesis = synthesis.strip()
        except Exception:
            pass

    return CouncilResult(
        council_results=list(council_results),
        synthesis=synthesis,
        question=question,
        members=len(personae),
        personae=[{"name": n, "persona": p} for n, p in personae],
    )
