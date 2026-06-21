"""风格特征管理 + 比喻注入 + 输出后清理"""

from __future__ import annotations

import json
import re
from pathlib import Path


class StyleProcessor:
    """风格特征：语境感知比喻注入 + 禁止短语过滤"""

    def __init__(self):
        self.features = self._load()
        self._metaphors: list[dict] = self.features.get("metaphors", [])
        self._prohibited: list[str] = self.features.get("prohibited_phrases", [])
        self._load_custom_blocks()

    def _load_custom_blocks(self):
        """从 ~/.qiushi/custom_blocks.json 加载用户自定义禁止短语"""
        path = Path.home() / ".qiushi" / "custom_blocks.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                extra = data.get("forbidden_phrases", [])
                if extra:
                    self._prohibited = list(dict.fromkeys(self._prohibited + extra))
            except (json.JSONDecodeError, OSError):
                pass

    def _load(self) -> dict:
        path = Path(__file__).resolve().parent.parent.parent / "style" / "features.json"
        default = {"metaphors": [], "prohibited_phrases": [], "prefix_statements": [], "strictness_tones": {}}
        if not path.exists():
            return default
        return {**default, **json.loads(path.read_text(encoding="utf-8"))}

    def filter_metaphors_by_scenario(self, scenario: str | None = None) -> list[dict]:
        """按场景过滤比喻库"""
        if not scenario or scenario == "general":
            return self._metaphors
        result = [m for m in self._metaphors if scenario in m.get("scenario", [])]
        return result if result else self._metaphors

    def build_style_prompt(self, query: str = "", scenario: str | None = None) -> tuple[str, list[str]]:
        """根据用户输入的语境，匹配并注入相关比喻

        返回:
            (prompt文本, 使用的比喻列表)
        """
        metaphors = self.filter_metaphors_by_scenario(scenario)
        if not metaphors:
            return "", []

        query_words = set(re.findall(r"[一-鿿]{2,}", query))

        scored = []
        for m in metaphors:
            trigger = m["trigger"]
            score = 0
            for w in query_words:
                if trigger in w or w in trigger:
                    score += 1
            if score > 0:
                scored.append((score, m))

        lines = []
        if scored:
            scored.sort(key=lambda x: -x[0])
            for _, m in scored[:2]:
                lines.append(f"- {m['full']}")
        # 如果无匹配，不随机选取比喻 — 不要硬塞

        if not lines:
            return "", []

        prompt = (
            "以下比喻跟当前话题有关，话说到了就自然带出来，没到别硬塞：\n"
            + "\n".join(lines)
        )
        return prompt, [m["full"] for _, m in scored[:2]]

    def sanitize(self, text: str) -> str:
        text = self._remove_headers(text)
        text = self._collapse_lists(text)
        text = self._filter_prohibited(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(line.strip() for line in text.split("\n")).strip()
        return text

    def _remove_headers(self, text: str) -> str:
        text = re.sub(r"^#{1,4}\s+.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*{2}([^*]+)\*{2}", r"\1", text)
        text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
        return re.sub(r"^[一二三四五六七八九十]+[、，,]\s*", "", text, flags=re.MULTILINE)

    def _collapse_lists(self, text: str) -> str:
        lines = text.split("\n")
        result = []
        buffer = []
        in_list = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    result.append("；".join(buffer) + "。")
                    buffer = []
                    in_list = False
                result.append("")
                continue
            is_item = bool(re.match(r"^(?:\d+[\.\)、]|[-*•·])\s+", stripped))
            if is_item:
                cleaned = re.sub(r"^(?:\d+[\.\)、]|[-*•·])\s+", "", stripped)
                buffer.append(cleaned)
                in_list = True
            else:
                if in_list:
                    result.append("；".join(buffer) + "。")
                    buffer = []
                    in_list = False
                result.append(stripped)
        if in_list and buffer:
            result.append("；".join(buffer) + "。")
        return "\n".join(result)

    def filter_prohibited(self, text: str) -> str:
        for phrase in self._prohibited:
            text = text.replace(phrase, "（就事论事）")
        return text

    def _filter_prohibited(self, text: str) -> str:
        return self.filter_prohibited(text)

    def get_prohibited_phrases(self) -> list[str]:
        return list(self._prohibited)
