"""输入分析 — 概念炼金术 + 矛盾检测 + 历史透视 + 段落解析"""

from __future__ import annotations

import json
from pathlib import Path


# ── 概念炼金术触发词 ─────────────────────────────────────────────

_CONCEPT_TRIGGERS = {
    "累": ["累", "疲惫", "没劲", "不想动", "没力气"],
    "迷茫": ["迷茫", "不知道", "没有方向", "不确定", "找不到方向"],
    "压力": ["压力", "焦虑", "紧张", "喘不过气", "扛不住"],
    "没意义": ["没意义", "活着没意思", "空虚", "无聊", "没劲透了"],
    "来不及": ["来不及", "晚了", "太迟", "错过", "30岁"],
}

# ── 矛盾类型检测 ────────────────────────────────────────────────

_CONTRADICTION_TYPES = {
    "职业选择": ["辞职", "跳槽", "转行", "offer", "面试", "被裁", "找不到工作", "该不该去"],
    "感情关系": ["分手", "吵架", "恋爱", "结婚", "女朋友", "男朋友", "离婚", "出轨"],
    "人生意义": ["迷茫", "意义", "活着", "找不到方向", "不知道干嘛"],
    "学习成长": ["书", "学习", "技能", "读书", "技术", "提升"],
    "财务管理": ["钱", "收入", "买房", "储蓄", "房贷", "不够花"],
}

# ── 历史透视触发词 ───────────────────────────────────────────────

_MACRO_TRIGGERS = {
    "30岁": "这个问题带有代际背景。把用户的年龄焦虑放在时代变迁的背景里看，他个人的困境可能不是他一个人的问题。",
    "转行": "这个问题带有行业结构性背景。考虑行业周期和时代变化对个人选择的影响。",
    "35岁": "这个问题带有职场结构性背景。35岁焦虑是特定时代产物，不是个人能力问题。",
    "裁员": "这是个结构性问题。把行业周期和公司决策作为大背景考虑。",
    "买房": "把房价变迁和代际财富差异作为背景考虑。",
}

# ── 段式解析 ─────────────────────────────────────────────────────


def parse_sections(text: str) -> dict[str, str]:
    """从 LLM 回复中提取 【分析】【反思】【总结】三段"""
    import re
    sections = {"main": "", "rebuttal": "", "summary": ""}
    main_match = re.search(r"【分析】(.+?)(?=【反思】|$)", text, re.DOTALL)
    rebuttal_match = re.search(r"【反思】(.+?)(?=【总结】|$)", text, re.DOTALL)
    summary_match = re.search(r"【总结】(.+?)$", text, re.DOTALL)
    if main_match:
        sections["main"] = main_match.group(1).strip()
    if rebuttal_match:
        sections["rebuttal"] = rebuttal_match.group(1).strip()
    if summary_match:
        sections["summary"] = summary_match.group(1).strip()
    if not main_match:
        sections["main"] = text
    return sections


# ── 分析器 ───────────────────────────────────────────────────────


class Analyzer:
    """统一输入分析器：概念炼金术 + 矛盾检测 + 历史透视 + 控制注入"""

    def __init__(self):
        self._custom_alchemy: dict | None = None

    def load_custom_alchemy(self) -> dict:
        """从 ~/.qiushi/alchemy_words.json 加载用户自定义词典"""
        if self._custom_alchemy is not None:
            return self._custom_alchemy
        path = Path.home() / ".qiushi" / "alchemy_words.json"
        if path.exists():
            self._custom_alchemy = json.loads(path.read_text(encoding="utf-8"))
        else:
            self._custom_alchemy = {}
        return self._custom_alchemy

    def analyze(self, user_input: str) -> dict:
        """分析用户输入，返回结构化结果"""
        result = {
            "matched_concepts": [],
            "matched_contradictions": [],
            "matched_macro": None,
            "injects": [],
        }

        # 1. 概念炼金术
        matched_concepts = []
        for concept, triggers in _CONCEPT_TRIGGERS.items():
            if any(t in user_input for t in triggers):
                matched_concepts.append(concept)
        custom = self.load_custom_alchemy()
        for concept, instruction in custom.items():
            if concept in user_input:
                matched_concepts = [c for c in matched_concepts if c != concept]
                matched_concepts.append(concept)
                result["injects"].append(f"注意：用户用了「{concept}」这个词。{instruction}")
                break
        if matched_concepts and not any(concept in custom for concept in matched_concepts):
            result["injects"].append(
                f"注意：用户用了「{matched_concepts[0]}」这个词。先想想这个描述是不是真的准确。"
                "有没有更贴切的描述？如果是，在分析中自然地重新定义它。"
            )
        result["matched_concepts"] = matched_concepts

        # 2. 矛盾类型检测
        matched_contradictions = []
        for ctype, triggers in _CONTRADICTION_TYPES.items():
            if any(t in user_input for t in triggers):
                matched_contradictions.append(ctype)
        if matched_contradictions:
            result["injects"].append(
                f"注意：用户的问题属于「{matched_contradictions[0]}」领域的矛盾。"
                "分析时重点抓住这个领域的主要矛盾，不要泛泛而谈。"
            )
        result["matched_contradictions"] = matched_contradictions

        # 3. 历史透视
        matched_macro = None
        for trigger, instruction in _MACRO_TRIGGERS.items():
            if trigger in user_input:
                result["injects"].append(f"注意：{instruction}")
                matched_macro = trigger
                break
        result["matched_macro"] = matched_macro

        # 4. 追问引导
        result["injects"].append("回答末尾，自然带出2-3个具体的下一步选项或追问方向，让用户可以选择继续往哪走。")

        return result
