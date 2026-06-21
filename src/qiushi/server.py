"""FastAPI HTTP API 服务器 — 懒加载"""


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """启动 API 服务器（懒导入 fastapi）"""
    try:
        from fastapi import FastAPI
        from fastapi.responses import StreamingResponse
        from pydantic import BaseModel
        from fastapi import Body
    except ImportError:
        import sys
        print("需要安装 fastapi 和 uvicorn: pip install 'qiushi[server]'", file=sys.stderr)
        sys.exit(1)

    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="求是 API", version="0.3.0", description="以哲学思辨为框架的 AI 思考伙伴")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    import json
    import uuid
    from typing import AsyncGenerator

    from .engine import QiuShiEngine
    from .config import QiushiConfig, CONFIG_DIR
    from .identity import get_or_create_user_id, profile_summary
    from .retriever import KnowledgeRetriever

    # ── 全局资源（懒加载） ──────────────────────────────────────
    _engine = None
    _knowledge = None

    def _get_engine():
        nonlocal _engine
        if _engine is None:
            config = QiushiConfig.load()
            vault = config.obsidian_vault or ""
            _engine = QiuShiEngine(config=config, obsidian_vault=vault or None)
        return _engine

    def _get_knowledge():
        nonlocal _knowledge
        if _knowledge is None:
            _knowledge = KnowledgeRetriever()
        return _knowledge

    # ── 路由 ──────────────────────────────────────────────────

    @app.get("/api/status")
    async def get_status() -> dict:
        db_path = CONFIG_DIR / "qiushi.db"
        config = QiushiConfig.load()
        kr = _get_knowledge()
        kr._ensure_loaded()
        return {
            "db_ok": db_path.exists(),
            "config_ok": bool(config.get_effective_api_key() or config.llm.provider == "ollama"),
            "llm_configured": bool(config.llm.api_key or config.get_effective_api_key()),
            "knowledge_files": len(kr.documents),
            "server_version": "0.3.0",
        }

    class ChatRequest(BaseModel):
        message: str
        session_id: str | None = None
        depth: int = 2

    @app.post("/api/chat")
    async def chat(req: ChatRequest = Body()):
        engine = _get_engine()
        sid = req.session_id or str(uuid.uuid4())[:8]

        async def event_stream():
            yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"
            async with engine:
                try:
                    async for token in engine.process_stream(sid, req.message, depth=req.depth):
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                    return
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/chat/sync")
    async def chat_sync(req: ChatRequest = Body()) -> dict:
        engine = _get_engine()
        sid = req.session_id or str(uuid.uuid4())[:8]
        async with engine:
            result = await engine.process_with_result(sid, req.message, depth=req.depth)
        return {
            "session_id": sid,
            "reply": result.public_text,
            "internals": {
                "concepts": result.matched_concepts,
                "contradictions": result.matched_contradictions,
                "macro": result.matched_macro,
                "knowledge_sources": [
                    {"title": r.get("title", ""), "quality": r.get("match_quality", "low")}
                    for r in result.knowledge_results
                ],
            },
        }

    @app.get("/api/profile")
    async def profile() -> dict:
        uid = get_or_create_user_id()
        summary = profile_summary(uid)
        return {
            "user_id": uid,
            "conversation_count": summary["conversation_count"],
            "contradictions": summary["contradictions"],
            "decisions": summary["decisions"],
            "strictness": summary["strictness"],
            "execution_rate": summary["execution_rate"],
        }

    @app.get("/api/knowledge")
    async def knowledge(q: str = "", limit: int = 10) -> dict:
        kr = _get_knowledge()
        if not q:
            return {"results": [], "total": 0}
        results = await kr.retrieve(q, top_k=limit)
        return {
            "results": [
                {"title": r.get("title", ""), "source": r.get("source", ""),
                 "content": r.get("content", "")[:200], "quality": r.get("match_quality", "low")}
                for r in results
            ],
            "total": len(results),
        }

    # ── 启动 ──────────────────────────────────────────────────
    import uvicorn
    print(f"求是 API 服务器 → http://{host}:{port}")
    print(f"  POST /api/chat        流式对话")
    print(f"  POST /api/chat/sync   同步对话")
    print(f"  GET  /api/profile     用户画像")
    print(f"  GET  /api/knowledge   知识检索")
    print(f"  GET  /api/status      系统状态")
    uvicorn.run(app, host=host, port=port)
