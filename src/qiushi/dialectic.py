"""苏格拉底式追问链：多轮辩证对话，支持保存/恢复"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from .engine import QiuShiEngine, ProcessResult
from .llm import LLMError

_SESSION_DIR = Path.home() / ".qiushi" / "sessions"


class DialecticSession:
    """管理多轮追问链的状态，支持保存/恢复"""

    def __init__(self, max_rounds: int = 3, session_id: str | None = None):
        self.max_rounds = max_rounds
        self.round = 0
        self.history: list[dict] = []
        self.results: list[ProcessResult] = []
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._question: str = ""

    # ── 保存/恢复 ──────────────────────────────────────────────────

    def _state_path(self) -> Path:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        return _SESSION_DIR / f"{self._session_id}.json"

    def save(self):
        """保存当前状态（不保存ProcessResult对象，只存文本）"""
        data = {
            "session_id": self._session_id,
            "question": self._question,
            "max_rounds": self.max_rounds,
            "round": self.round,
            "history": self.history,
            "responses": [r.public_text for r in self.results],
        }
        self._state_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, session_id: str) -> "DialecticSession | None":
        path = _SESSION_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        s = cls(max_rounds=data["max_rounds"], session_id=session_id)
        s._question = data.get("question", "")
        s.round = data["round"]
        s.history = data["history"]
        # 将保存的文本重建为最小 ProcessResult（仅用于 synthesize）
        for resp in data.get("responses", []):
            s.results.append(ProcessResult(
                reply=resp, sections={"main": resp, "rebuttal": "", "summary": ""},
                knowledge_results=[], matched_concepts=[], matched_macro=None,
                matched_contradictions=[], metaphors_used=[], depth=2, auto_saved=False,
            ))
        return s

    @classmethod
    def list_sessions(cls) -> list[dict]:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for f in sorted(_SESSION_DIR.iterdir()):
            if f.suffix == ".json":
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data.get("session_id", f.stem),
                    "question": data.get("question", "?")[:60],
                    "round": data.get("round", 0),
                    "max_rounds": data.get("max_rounds", 3),
                })
        return sessions

    @classmethod
    def delete(cls, session_id: str):
        path = _SESSION_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()

    # ── 核心逻辑 ───────────────────────────────────────────────────

    async def start(
        self, engine: QiuShiEngine, session_id: str, question: str, depth: int = 2,
    ) -> tuple[str, str | None]:
        self._question = question
        result = await engine.process_with_result(session_id, question, depth=depth)
        self.results.append(result)
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": result.public_text})
        self.round = 1
        self.save()

        if self.round >= self.max_rounds:
            return self._synthesize(), None

        follow_up = await self._generate_follow_up(engine, session_id, question)
        return result.public_text, follow_up

    async def continue_(
        self, engine: QiuShiEngine, session_id: str, user_response: str, original_question: str, depth: int = 2,
    ) -> tuple[str, str | None]:
        self.history.append({"role": "user", "content": user_response})
        self.round += 1

        context = f"原始问题：{original_question}\n\n我们已经讨论到第{self.round}轮。用户的最新回应：{user_response}"
        result = await engine.process_with_result(session_id, context, history=self.history[:-1], depth=depth)
        self.results.append(result)
        self.history.append({"role": "assistant", "content": result.public_text})
        self.save()

        if self.round >= self.max_rounds:
            return result.public_text, None

        follow_up = await self._generate_follow_up(engine, session_id, original_question)
        return result.public_text, follow_up

    async def _generate_follow_up(self, engine: QiuShiEngine, session_id: str, original_question: str) -> str:
        views = [r.public_text[:200] for r in self.results]
        context = (
            f"原始问题：{original_question}\n\n"
            f"目前已经讨论到的观点：\n" + "\n---\n".join(views) + "\n\n"
            f"基于以上对话，生成一个具有挑战性的追问。不要重复已经问过的问题，"
            f"要从一个还没有被充分探讨的角度切入。只输出追问本身，不要前缀。"
        )
        try:
            follow_up = await engine._llm.chat(
                [{"role": "user", "content": context}],
                system="你是一个苏格拉底式的追问者。你的任务是找到对方思考中的盲点，用一个问题引导他看到自己没有看到的角度。",
                temperature=0.7,
            )
            return follow_up.strip()
        except LLMError:
            return "你还有其他角度想探讨的吗？"

    def _synthesize(self) -> str:
        parts = ["══ 辩证总结 ══"]
        for i, r in enumerate(self.results):
            parts.append(f"\n第{i+1}轮核心观点：")
            parts.append(r.sections.get("main", r.public_text)[:300])
        last = self.results[-1]
        parts.append("\n\n最终总结：" if last.sections.get("summary") else "\n\n")
        if last.sections.get("summary"):
            parts.append(last.sections["summary"])
        return "\n".join(parts)
