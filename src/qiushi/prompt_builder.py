"""Prompt 构建 — system prompt 组装 + token 预算 + 记忆上下文"""

from __future__ import annotations

from .config import resolve_prompt


class PromptBuilder:
    """system prompt 构建器，含 token 预算控制和优先级裁剪"""

    def __init__(self):
        self._system_prompt_cache: str | None = None
        self._system_prompt_deep_cache: str | None = None

    def build_messages(self, user_input: str, history: list[dict] | None = None) -> list[dict]:
        """构建 LLM messages 数组"""
        messages: list[dict] = []
        if history:
            for h in history[-4:]:
                if h.get("user"):
                    messages.append({"role": "user", "content": h["user"]})
                if h.get("assistant"):
                    messages.append({"role": "assistant", "content": h["assistant"]})
        messages.append({"role": "user", "content": user_input})
        return messages

    def build_memory_context(self, conversations: list[dict] | list | None) -> str:
        """构建对话记忆片段"""
        if not conversations:
            return ""
        recent = conversations[-3:]
        lines = ["\n## 你们之前聊过这些"]
        for c in recent:
            if "role" in c:
                user_part = c.get("content", "")[:80]
                assistant_part = ""
            else:
                user_part = c.get("user", "")[:80]
                assistant_part = c.get("assistant", "")[:80]
            lines.append(f"- 用户说：{user_part}")
            if assistant_part:
                lines.append(f"  你回：{assistant_part}")
        return "\n".join(lines)

    def build_system_prompt(
        self, base_prompt: str, knowledge_context: str = "",
        style_prompt: str = "", memory_context: str = "",
        control_injects: list[str] | None = None, depth: int = 2,
    ) -> str:
        """构建完整 system prompt，含优先级裁剪"""
        sections: list[tuple[int, str, str]] = [
            (1, "base", base_prompt),
        ]
        if control_injects:
            text = "\n".join(control_injects)
            sections.append((2, "controls", text))
        if knowledge_context:
            sections.append((3, "knowledge", knowledge_context))
        if memory_context:
            sections.append((4, "memory", memory_context))
        if style_prompt:
            sections.append((5, "style", style_prompt))

        budget = 2500
        extra = sum(len(text) for prio, _, text in sections if prio >= 3)
        if extra > budget:
            for prio in range(5, 2, -1):
                for i, (p, name, text) in enumerate(sections):
                    if p != prio:
                        continue
                    if extra <= budget:
                        break
                    max_len = max(len(text) // 3, 200)
                    truncated = text[:max_len] + "\n[以下内容因长度限制已截断]"
                    sections[i] = (p, name, truncated)
                    extra -= len(text) - len(truncated)
                if extra <= budget:
                    break

        sections.sort(key=lambda x: x[0])
        return "\n\n".join(text for _, _, text in sections)

    def get_system_prompt(self, depth: int = 2) -> str:
        """获取基础 system prompt，按 depth 添加尾部指令"""
        base = resolve_prompt("system.md")
        if depth == 1:
            suffix = (
                "\n\n## 快速分析\n"
                "简短回答，一段话说清楚核心判断，不展开多角度分析。"
            )
            if self._system_prompt_cache is None:
                self._system_prompt_cache = base + suffix
            return self._system_prompt_cache
        elif depth >= 3:
            suffix = (
                "\n\n## 深度分析\n"
                "从以下三个分析维度中至少选两个展开，不要只用一个角度：\n"
                "1. **正面看** — 问题本身的合理性、有利条件、可行之处\n"
                "2. **反面看** — 隐藏的假设、可能的盲区、反直觉的一面\n"
                "3. **历史看** — 类似情况在时间维度上的变化趋势，不是简单复述过去\n"
                "在每个维度末尾标注你对这个角度的信心度（高/中/低）。"
                "深入比简短重要，不要怕分析太长。"
            )
            if self._system_prompt_deep_cache is None:
                self._system_prompt_deep_cache = base + suffix
            return self._system_prompt_deep_cache
        return base
