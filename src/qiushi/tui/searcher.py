"""网络搜索工具 — 获取最新资讯供思辨使用"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)


class WebSearcher:
    """网络搜索器 — 获取最新资讯"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=12.0,
                follow_redirects=True,
                headers=self._headers,
            )

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """搜索网络，返回结构化的搜索结果"""
        await self._ensure_client()
        if not self._client:
            return []

        # 主要策略：Bing 搜索
        try:
            results = await self._search_bing(query, max_results)
            if results:
                return results
        except Exception as e:
            logger.debug(f"Bing 搜索失败: {e}")

        return []

    async def _search_bing(self, query: str, max_results: int) -> list[dict]:
        """Bing 搜索"""
        resp = await self._client.get(
            "https://www.bing.com/search",
            params={"q": query, "setlang": "zh-CN"},
        )
        resp.raise_for_status()

        results = []
        text = resp.text

        # 方法1：Bing 的标准搜索结果格式 <li class="b_algo">
        pattern1 = re.compile(
            r'<li[^>]*class="b_algo"[^>]*>.*?<h2><a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        for href, title_html in pattern1.findall(text):
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            if title:
                results.append({"title": title, "body": "", "href": href})
                if len(results) >= max_results:
                    break

        # 方法2：备用模式
        if not results:
            pattern2 = re.compile(
                r'<h2><a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            seen = set()
            for href, title_html in pattern2.findall(text):
                title = re.sub(r"<[^>]+>", "", title_html).strip()
                # 过滤掉导航/广告链接
                if title and not any(
                    d in href for d in ["bing.com", "microsoft.com"]
                ):
                    if href not in seen:
                        seen.add(href)
                        results.append(
                            {"title": title, "body": "", "href": href}
                        )
                        if len(results) >= max_results:
                            break

        # 方法3：通用链接提取（兜底）
        if not results:
            pattern3 = re.compile(
                r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL
            )
            seen = set()
            for href, title_html in pattern3.findall(text):
                title = re.sub(r"<[^>]+>", "", title_html).strip()
                if (
                    title
                    and len(title) > 5
                    and not any(
                        d in href
                        for d in [
                            "bing.com",
                            "microsoft.com",
                            "go.microsoft.com",
                        ]
                    )
                ):
                    if href not in seen:
                        seen.add(href)
                        results.append(
                            {"title": title, "body": "", "href": href}
                        )
                        if len(results) >= max_results:
                            break

        return results

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def format_context(self, results: list[dict]) -> str:
        """将搜索结果格式化为 LLM 上下文"""
        if not results:
            return ""

        lines = ["以下是最新搜索到的相关信息：\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"[{i}] {title}")
            if body:
                lines.append(f"    {body}")
            if href:
                lines.append(f"    [来源: {href}]")
            lines.append("")

        return "\n".join(lines)

    async def search_and_format(self, query: str, max_results: int = 5) -> str:
        """搜索并直接返回格式化上下文"""
        results = await self.search(query, max_results)
        return self.format_context(results)
