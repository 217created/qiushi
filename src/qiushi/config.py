"""统一配置系统"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_DIR = Path.home() / ".qiushi"
CONFIG_PATH = CONFIG_DIR / "config.json"

# 内置资源路径（pip install 后的 site-packages 路径）
_BUILTIN_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILTIN_KNOWLEDGE = _BUILTIN_ROOT / "knowledge"


# ── 内置默认哲学人格流派 ──────────────────────────────────────
DEFAULT_PERSONAE: list[dict] = [
    # 西方哲学 · 古代
    {"name": "亚里士多德", "desc": "关注目的因、中庸之道、实践智慧，追求德性与幸福主义的统一", "active": True, "group": "西方·古代"},
    {"name": "柏拉图", "desc": "关注理念论、洞穴寓言、灵魂三分，追求善的理念与真理", "active": True, "group": "西方·古代"},
    {"name": "伊壁鸠鲁", "desc": "关注快乐主义、心灵宁静，追求原子论基础上的无惧生活", "active": True, "group": "西方·古代"},
    # 西方哲学 · 近代
    {"name": "笛卡尔", "desc": "关注我思故我在、身心二元论，以理性怀疑为方法构建确定性", "active": True, "group": "西方·近代"},
    {"name": "康德", "desc": "关注先验统觉、道德律令、判断力批判，调和理性主义与经验主义", "active": True, "group": "西方·近代"},
    {"name": "边沁", "desc": "关注最大多数人的最大幸福原则、功利计算，以快乐痛苦权衡为道德基础", "active": True, "group": "西方·近代"},
    {"name": "密尔", "desc": "关注功利主义的质化改良、个体自由与社会权力的边界", "active": True, "group": "西方·近代"},
    # 西方哲学 · 现代
    {"name": "尼采", "desc": "关注权力意志、超人哲学、永恒轮回，批判传统道德与虚无主义", "active": True, "group": "西方·现代"},
    {"name": "萨特", "desc": "关注存在先于本质、自由选择与绝对责任、他者即地狱", "active": True, "group": "西方·现代"},
    {"name": "维特根斯坦", "desc": "关注语言界限、语言游戏、沉默是对不可言说者的尊重", "active": True, "group": "西方·现代"},
    {"name": "海德格尔", "desc": "关注此在、在世存在、向死而生、技术的本质追问", "active": True, "group": "西方·现代"},
    {"name": "罗尔斯", "desc": "关注正义即公平、无知之幕、差别原则，构建社会契约论", "active": True, "group": "西方·现代"},
    # 东方哲学
    {"name": "孔子", "desc": "关注仁者爱人、礼乐教化、中庸之道，以修身齐家治国平天下为理想", "active": True, "group": "东方"},
    {"name": "老子", "desc": "关注道法自然、无为而治、柔弱胜刚强，以天道观照人世", "active": True, "group": "东方"},
    {"name": "庄子", "desc": "关注逍遥游、齐物论、无用之用，超越是非生死之外的自由之境", "active": True, "group": "东方"},
    {"name": "佛陀", "desc": "关注一切皆苦、缘起性空、八正道，以离苦得乐为终极关怀", "active": True, "group": "东方"},
    {"name": "韩非子", "desc": "关注法、术、势三者结合，人性自利的现实主义治国思想", "active": True, "group": "东方"},
    # 马克思主义 · 分析哲学 · 交叉
    {"name": "辩证唯物", "desc": "关注矛盾分析、实践检验、历史唯物主义，结构性社会批判视角", "active": True, "group": "现代批判"},
    {"name": "法兰克福学派", "desc": "关注文化工业、工具理性批判、启蒙辩证法，诊断现代性病症", "active": True, "group": "现代批判"},
    {"name": "福柯", "desc": "关注权力—知识共生、规训社会、性话语，解构看似自然的制度安排", "active": True, "group": "现代批判"},
    {"name": "阿伦特", "desc": "关注极权主义起源、公共领域、平庸之恶、行动与劳动的区别", "active": True, "group": "现代批判"},
    # 实践哲学
    {"name": "斯多葛", "desc": "关注可控与不可控的界限、理性、克制和内在平静", "active": True, "group": "实践哲学"},
    {"name": "存在主义", "desc": "关注自由选择、个体责任、意义的自我创造", "active": True, "group": "实践哲学"},
    {"name": "实用主义", "desc": "关注知识的效果与可检验性、真理即有用、思想作为行动指南", "active": True, "group": "实践哲学"},
    {"name": "女权主义", "desc": "关注性别权力结构、他者化批判、交叉性分析，重新审视知识建构中的性别盲区", "active": True, "group": "实践哲学"},
]


@dataclass
class LLMConfig:
    provider: str = "deepseek"       # deepseek / openai / anthropic / ollama / openrouter
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = ""               # 空=provider默认
    timeout: int = 120


@dataclass
class PersonaDef:
    """单个哲学人格定义"""
    name: str = ""
    desc: str = ""
    active: bool = True
    group: str = "其他"


@dataclass
class QiushiConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    obsidian_vault: str = ""         # 空=不启用
    personae: list[PersonaDef] = field(default_factory=list)

    @classmethod
    def load(cls) -> "QiushiConfig":
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            return cls._from_dict(raw)
        return cls._from_dict({"personae": DEFAULT_PERSONAE})

    @classmethod
    def _from_dict(cls, raw: dict) -> "QiushiConfig":
        llm_raw = raw.get("llm", {})
        personae_raw = raw.get("personae", DEFAULT_PERSONAE)
        return cls(
            llm=LLMConfig(
                provider=llm_raw.get("provider", "deepseek"),
                model=llm_raw.get("model", "deepseek-chat"),
                api_key=llm_raw.get("api_key", ""),
                base_url=llm_raw.get("base_url", ""),
                timeout=llm_raw.get("timeout", 120),
            ),
            obsidian_vault=raw.get("obsidian_vault", ""),
            personae=[PersonaDef(**p) if isinstance(p, dict) else PersonaDef(name=p) for p in personae_raw],
        )

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        return {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key": self.llm.api_key,
                "base_url": self.llm.base_url,
                "timeout": self.llm.timeout,
            },
            "obsidian_vault": self.obsidian_vault,
            "personae": [{"name": p.name, "desc": p.desc, "active": p.active, "group": p.group} for p in self.personae],
        }

    def get_active_personae(self) -> list[PersonaDef]:
        """获取活跃的人格列表"""
        return [p for p in self.personae if p.active]

    def get_personae_by_group(self) -> dict[str, list[PersonaDef]]:
        """按流派分组"""
        groups: dict[str, list[PersonaDef]] = {}
        for p in self.personae:
            if not p.active:
                continue
            groups.setdefault(p.group, []).append(p)
        return groups

    def get_effective_api_key(self) -> str:
        """从配置或环境变量中获取 API key"""
        if self.llm.api_key:
            return self.llm.api_key
        # 按 provider 查找对应环境变量
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        env_var = env_map.get(self.llm.provider, "")
        return os.getenv(env_var, "")


# ── 用户自定义资源路径 ────────────────────────────────────────────

USER_KNOWLEDGE_DIR = CONFIG_DIR / "knowledge"
USER_PROMPT_DIR = CONFIG_DIR / "prompts"


def resolve_prompt(name: str) -> str:
    """返回prompt文件内容：用户目录优先，fallback到内置"""
    # 内置路径
    builtin = _BUILTIN_ROOT / "prompts" / name
    # 用户自定义路径
    user = USER_PROMPT_DIR / name

    target = user if user.exists() else builtin
    return target.read_text(encoding="utf-8")


def resolve_prompt_path(name: str) -> Path:
    user = USER_PROMPT_DIR / name
    return user if user.exists() else _BUILTIN_ROOT / "prompts" / name


def get_knowledge_roots() -> list[tuple[Path, str]]:
    """返回 (目录路径, 标签) 列表。用户目录优先于内置。"""
    roots: list[tuple[Path, str]] = []
    if USER_KNOWLEDGE_DIR.exists():
        for subdir in sorted(USER_KNOWLEDGE_DIR.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith("."):
                roots.append((subdir, subdir.name))
    if _BUILTIN_KNOWLEDGE.exists():
        for subdir in sorted(_BUILTIN_KNOWLEDGE.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith("."):
                # 用户已覆盖的目录不再加
                if not any(r[1] == subdir.name for r in roots):
                    roots.append((subdir, subdir.name))
    return roots
