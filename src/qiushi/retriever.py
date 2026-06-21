"""知识库检索 — 关键词倒排索引 + 知识关系层 + LRU缓存"""

from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path

from .config import get_knowledge_roots
from .adapter import load_adapters

_LOW_CONFIDENCE_THRESHOLD = 3
_CACHE_MAX_SIZE = 100


class _LRUCache:
    """简单的LRU缓存，用于知识检索结果"""

    def __init__(self, maxsize: int = _CACHE_MAX_SIZE):
        self._maxsize = maxsize
        self._cache: dict[str, list[dict]] = {}
        self._order: list[str] = []

    def get(self, key: str) -> list[dict] | None:
        if key not in self._cache:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._cache[key]

    def put(self, key: str, value: list[dict]):
        if key in self._cache:
            self._order.remove(key)
        elif len(self._order) >= self._maxsize:
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._order.append(key)

    def clear(self):
        self._cache.clear()
        self._order.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class KnowledgeRetriever:
    """关键词检索 + 知识关系提示 + LRU缓存"""

    def __init__(self):
        self.documents: list[dict] = []
        self.index: dict[str, list[int]] = {}
        self.relations: list[dict] = []
        self._cache = _LRUCache()
        self._loaded = False

    def _ensure_loaded(self):
        """懒加载：首次检索时才加载知识库"""
        if not self._loaded:
            self._load_all()

    def _load_all(self):
        if self._loaded:
            return
        for root_dir, label in get_knowledge_roots():
            self._load_dir(root_dir, label)
        self._load_connections()
        self._load_adapters()
        self._loaded = True

    def _load_adapters(self):
        """加载外部适配器中的 .md 文件"""
        adapters = load_adapters()
        for adapter in adapters:
            for fpath in adapter.list_files():
                self._load_file(fpath, f"adapter:{adapter.name()}")

    def reload(self):
        """手动刷新：清空缓存并重新加载。注意：正在运行的 engine 需要重启才会使用新数据。"""
        self._cache.clear()
        self.documents.clear()
        self.index.clear()
        self.relations.clear()
        self._loaded = False
        self._load_all()

    def _load_dir(self, root_dir: Path, label: str):
        for fname in sorted(root_dir.iterdir()):
            if not fname.suffix == ".md":
                continue
            self._load_file(fname, f"{label}/{fname.stem}")

    def _load_file(self, fpath: Path, source: str):
        """加载单个 .md 文件到索引"""
        content = fpath.read_text(encoding="utf-8")
        title = ""
        for line in content.split("\n"):
            if line.strip().startswith("# "):
                title = line.strip().lstrip("# ").strip()
                break
        for para in content.split("\n\n"):
            para = para.strip()
            if len(para) < 20:
                continue
            clean = para.replace("> ", "")
            is_application = "如何用在生活中" in para
            idx = len(self.documents)
            self.documents.append({
                "source": source,
                "title": title,
                "is_application": is_application,
                "content": clean[:500],
            })
            for w in set(re.findall(r"[一-鿿]{2,}", clean)):
                self.index.setdefault(w, []).append(idx)
                for i in range(len(w) - 1):
                    bigram = w[i:i+2]
                    self.index.setdefault(bigram, []).append(idx)

    def _load_connections(self):
        for root_dir, _ in get_knowledge_roots():
            conn_file = root_dir / "_connections.json"
            if conn_file.exists():
                data = json.loads(conn_file.read_text(encoding="utf-8"))
                self.relations.extend(data.get("relations", []))

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        self._ensure_loaded()
        if not self.documents:
            return []

        # LRU 缓存命中
        cache_key = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        query_words = set(re.findall(r"[一-鿿]{2,}", query))
        bigrams: set[str] = set()
        for w in query_words:
            for i in range(len(w) - 1):
                bigrams.add(w[i:i+2])
        all_terms = query_words | bigrams
        scores: dict[int, int] = {}
        for w in all_terms:
            for idx in self.index.get(w, []):
                scores[idx] = scores.get(idx, 0) + 1
        if not scores:
            return []
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        results = []
        for idx, score in ranked:
            doc = dict(self.documents[idx])
            doc["match_score"] = score
            doc["match_quality"] = "high" if score >= _LOW_CONFIDENCE_THRESHOLD else "low"
            results.append(doc)

        self._cache.put(cache_key, results)
        return results

    def format_context(self, results: list[dict]) -> str:
        if not results:
            return ""
        parts = ["\n参考以下内容来回答问题："]
        seen = set()
        high_quality = any(r.get("match_quality") == "high" for r in results)
        if not high_quality:
            parts.append("（注：以下参考内容可能与问题不完全匹配，请结合自身知识回答）")
        for r in results:
            key = r["content"][:40]
            if key in seen:
                continue
            seen.add(key)
            prefix = "用法" if r.get("is_application") else "原文"
            parts.append(f"> [{prefix}] 摘自《{r['title']}》— {r['content']}")
        if self.relations:
            relation_hints = []
            for rel in self.relations:
                titles = {r["title"] for r in results}
                if rel["from"] in titles or rel["to"] in titles:
                    relation_hints.append(f"思想关联：{rel['from']} ↔ {rel['to']} → {rel.get('relation', '')}")
            if relation_hints:
                parts.append("\n可参考以下思想关联：")
                parts.extend(relation_hints)
        return "\n".join(parts)
