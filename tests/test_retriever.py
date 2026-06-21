"""知识检索测试"""

import pytest
from qiushi.retriever import KnowledgeRetriever


@pytest.mark.asyncio
async def test_retriever_loads():
    """知识库加载不报错"""
    kr = KnowledgeRetriever()
    kr._ensure_loaded()
    assert len(kr.documents) > 0


@pytest.mark.asyncio
async def test_retriever_search():
    """关键词检索返回结果"""
    kr = KnowledgeRetriever()
    results = await kr.retrieve("矛盾")
    assert len(results) > 0
    assert "content" in results[0]


@pytest.mark.asyncio
async def test_retriever_empty_query():
    """空查询返回空列表"""
    kr = KnowledgeRetriever()
    results = await kr.retrieve("")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_retriever_format_context():
    """format_context 不报错"""
    kr = KnowledgeRetriever()
    results = await kr.retrieve("实践")
    text = kr.format_context(results)
    assert isinstance(text, str)
    assert len(text) > 0
