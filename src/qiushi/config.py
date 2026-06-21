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


@dataclass
class LLMConfig:
    provider: str = "deepseek"       # deepseek / openai / anthropic / ollama / openrouter
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = ""               # 空=provider默认
    timeout: int = 120


@dataclass
class QiushiConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    obsidian_vault: str = ""         # 空=不启用

    @classmethod
    def load(cls) -> "QiushiConfig":
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            return cls._from_dict(raw)
        return cls()

    @classmethod
    def _from_dict(cls, raw: dict) -> "QiushiConfig":
        llm_raw = raw.get("llm", {})
        return cls(
            llm=LLMConfig(
                provider=llm_raw.get("provider", "deepseek"),
                model=llm_raw.get("model", "deepseek-chat"),
                api_key=llm_raw.get("api_key", ""),
                base_url=llm_raw.get("base_url", ""),
                timeout=llm_raw.get("timeout", 120),
            ),
            obsidian_vault=raw.get("obsidian_vault", ""),
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
        }

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
