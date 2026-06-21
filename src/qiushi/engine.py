"""主引擎 — 单段式 LLM 思辨流水线"""

from __future__ import annotations

from typing import AsyncGenerator

from .analyzer import Analyzer, parse_sections
from .config import QiushiConfig
from .identity import (get_or_create_user_id, resolve_user_id, get_profile,
                         save_conversation, build_cross_session_context,
                         update_user_contradictions)
from .llm import LLMClient, LLMError, create_llm
from .prompt_builder import PromptBuilder
from .retriever import KnowledgeRetriever
from .style import StyleProcessor
from .db import upsert_contradiction, upsert_decision


class ProcessResult:
    """process() 的完整返回结果，包含回答和内部决策信息"""

    def __init__(
        self,
        reply: str,
        sections: dict[str, str],
        knowledge_results: list[dict],
        matched_concepts: list[str],
        matched_macro: str | None,
        matched_contradictions: list[str],
        metaphors_used: list[str],
        depth: int,
        auto_saved: bool,
    ):
        self.reply = reply
        self.sections = sections
        self.knowledge_results = knowledge_results
        self.matched_concepts = matched_concepts
        self.matched_macro = matched_macro
        self.matched_contradictions = matched_contradictions
        self.metaphors_used = metaphors_used
        self.depth = depth
        self.auto_saved = auto_saved

    @property
    def public_text(self) -> str:
        parts = []
        if self.sections.get("main"):
            parts.append(self.sections["main"])
        if self.sections.get("summary"):
            parts.append(self.sections["summary"])
        return "\n\n".join(parts)

    @property
    def full_text(self) -> str:
        return self.reply

    def to_json(self, question: str, show_think: bool = False) -> dict:
        d: dict = {
            "question": question,
            "depth": self.depth,
        }
        if show_think:
            d["answer"] = self.full_text
        else:
            d["answer"] = self.public_text
        d["internals"] = {
            "knowledge_sources": [
                {"source": r.get("source", ""), "title": r.get("title", ""),
                 "match_score": r.get("match_score", 0), "match_quality": r.get("match_quality", "low")}
                for r in self.knowledge_results
            ],
            "concept_alchemy_triggered": self.matched_concepts,
            "historical_perspective_triggered": self.matched_macro,
            "metaphors_used": self.metaphors_used,
            "sections": self.sections,
        }
        return d

    def to_explain_text(self, question: str) -> str:
        lines = [
            "══ 分析报告 ══",
            f"问题: {question}",
            f"深度: {self.depth}",
        ]
        if self.knowledge_results:
            lines.append("\n📚 知识引用:")
            for r in self.knowledge_results:
                quality = r.get("match_quality", "low")
                marker = "●" if quality == "high" else "○"
                lines.append(f"  {marker} 《{r.get('title', '?')}》 [{quality}, score={r.get('match_score', 0)}]")
        if self.matched_concepts:
            lines.append(f"\n🔍 概念炼金术触发: {', '.join(self.matched_concepts)}")
        if self.matched_macro:
            lines.append(f"\n📜 历史透视触发: {self.matched_macro}")
        if self.metaphors_used:
            lines.append(f"\n🧪 注入比喻: {', '.join(self.metaphors_used)}")
        if self.matched_contradictions:
            lines.append(f"\n📌 检测到矛盾类型: {', '.join(self.matched_contradictions)}")
        if self.auto_saved:
            lines.append(f"\n💾 已自动记录矛盾/决策到用户知识库")
        lines.append("\n══ 回答 ══")
        lines.append(self.public_text)
        return "\n".join(lines)


class QiuShiEngine:
    """求是主引擎 — 编排器"""

    def __init__(self, config: QiushiConfig | None = None, obsidian_vault: str | None = None):
        self._config = config or QiushiConfig.load()
        self._llm: LLMClient | None = None
        self._knowledge: KnowledgeRetriever | None = None
        self._style: StyleProcessor | None = None
        self._analyzer = Analyzer()
        self._prompt_builder = PromptBuilder()
        self._obsidian_vault = obsidian_vault or self._config.obsidian_vault
        self._user_id: str | None = None
        self._scenario: str = "general"

    # ── 生命周期 ──────────────────────────────────────────────────

    async def __aenter__(self):
        await self._ensure_llm()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        if self._llm:
            await self._llm.close()
            self._llm = None

    async def _ensure_llm(self):
        if self._llm is None:
            self._llm = create_llm(self._config)

    def _resolve_user(self, session_id: str | None = None):
        if self._user_id is None:
            if session_id:
                self._user_id = resolve_user_id(session_id)
            else:
                self._user_id = get_or_create_user_id()

    # ── 公开 API ──────────────────────────────────────────────────

    async def process(self, session_id: str, user_input: str, history: list[dict] | None = None,
                      depth: int = 2, show_think: bool = False) -> str:
        result = await self.process_with_result(session_id, user_input, history, depth)
        return result.full_text if show_think else result.public_text

    async def process_stream(self, session_id: str, user_input: str, history: list[dict] | None = None,
                             depth: int = 2, show_think: bool = False) -> AsyncGenerator[str, None]:
        """流式处理。"""
        await self._ensure_llm()

        if self._knowledge is None:
            self._knowledge = KnowledgeRetriever()
        knowledge_results = await self._knowledge.retrieve(user_input)
        knowledge_context = self._knowledge.format_context(knowledge_results)

        if self._style is None:
            self._style = StyleProcessor()
        style_result = self._style.build_style_prompt(query=user_input, scenario=self._scenario)
        style_prompt, metaphors_used = style_result if isinstance(style_result, tuple) else (style_result, [])

        analysis = self._analyzer.analyze(user_input)
        self._resolve_user(session_id)
        profile = get_profile(self._user_id)
        memory_context = self._prompt_builder.build_memory_context(
            history or profile.get("conversations", [])
        )
        cross_session = build_cross_session_context(profile, analysis["matched_contradictions"])
        if cross_session:
            analysis["injects"].append(cross_session)
        base_prompt = self._prompt_builder.get_system_prompt(depth=depth)
        system = self._prompt_builder.build_system_prompt(
            base_prompt, knowledge_context, style_prompt, memory_context, analysis["injects"], depth=depth,
        )
        messages = self._prompt_builder.build_messages(user_input, history)

        full_reply = ""
        try:
            async for token in self._llm.chat_stream(messages, system=system):
                full_reply += token
                yield token
        except LLMError as e:
            error_msg = f"[系统提示] {e}"
            yield error_msg
            full_reply = error_msg

        reply = self._sanitize(full_reply)
        save_conversation(self._user_id, user_input, reply, self._obsidian_vault)

    async def process_with_result(self, session_id: str, user_input: str,
                                  history: list[dict] | None = None, depth: int = 2) -> ProcessResult:
        """完整处理，返回 ProcessResult 对象。"""
        await self._ensure_llm()

        # 1. 知识检索
        if self._knowledge is None:
            self._knowledge = KnowledgeRetriever()
        knowledge_results = await self._knowledge.retrieve(user_input)
        knowledge_context = self._knowledge.format_context(knowledge_results)

        # 2. 比喻注入
        if self._style is None:
            self._style = StyleProcessor()
        style_result = self._style.build_style_prompt(query=user_input, scenario=self._scenario)
        style_prompt, metaphors_used = style_result if isinstance(style_result, tuple) else (style_result, [])

        # 3. 分析输入（概念炼金术 + 矛盾 + 历史透视）
        analysis = self._analyzer.analyze(user_input)

        # 4. 读画像 + 记忆 + 跨 session 感知
        self._resolve_user(session_id)
        profile = get_profile(self._user_id)
        memory_context = self._prompt_builder.build_memory_context(
            history or profile.get("conversations", [])
        )
        cross_session = build_cross_session_context(profile, analysis["matched_contradictions"])
        if cross_session:
            analysis["injects"].append(cross_session)

        # 5. 构建 system prompt
        base_prompt = self._prompt_builder.get_system_prompt(depth=depth)
        system = self._prompt_builder.build_system_prompt(
            base_prompt, knowledge_context, style_prompt, memory_context,
            analysis["injects"], depth=depth,
        )

        # 6. 调用 LLM
        messages = self._prompt_builder.build_messages(user_input, history)
        try:
            reply = await self._llm.chat(messages, system=system)
        except LLMError as e:
            reply = f"[系统提示] {e}"

        reply = self._sanitize(reply)
        sections = parse_sections(reply)
        save_conversation(self._user_id, user_input, reply, self._obsidian_vault)

        # 7. 自动沉淀 + 更新画像
        auto_saved = False
        if analysis["matched_contradictions"]:
            for ct in analysis["matched_contradictions"]:
                upsert_contradiction(self._user_id, ct, user_input[:100])
            summary = sections.get("summary", "").strip()
            suggestion = summary[:100] if summary and len(summary) > 20 else ""
            if suggestion:
                upsert_decision(self._user_id, suggestion, analysis["matched_contradictions"][0])
            update_user_contradictions(self._user_id, analysis["matched_contradictions"],
                                       user_input, suggestion)
            auto_saved = True

        return ProcessResult(
            reply=reply, sections=sections,
            knowledge_results=knowledge_results,
            matched_concepts=analysis["matched_concepts"],
            matched_macro=analysis["matched_macro"],
            matched_contradictions=analysis["matched_contradictions"],
            metaphors_used=metaphors_used, depth=depth,
            auto_saved=auto_saved,
        )

    # ── 后处理 ────────────────────────────────────────────────────

    def _sanitize(self, text: str) -> str:
        if self._style is None:
            self._style = StyleProcessor()
        return self._style.filter_prohibited(text).strip()
