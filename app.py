"""求是 Web 版 — Streamlit 可展示化"""

from __future__ import annotations

import asyncio
import uuid

import streamlit as st

from qiushi.analyzer import parse_sections
from qiushi.config import QiushiConfig
from qiushi.engine import QiuShiEngine

st.set_page_config(
    page_title="求是 — 思辨，然后行动",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 样式 ───────────────────────────────────────────────────────

st.markdown("""
<style>
.section-label { font-size:0.85rem; font-weight:600; letter-spacing:0.02em; margin-bottom:0.4rem; }
.section-analysis .section-label { color:#3B82F6; }
.section-rebuttal .section-label { color:#F59E0B; }
.section-summary .section-label { color:#10B981; }
.placeholder-text { color:#9CA3AF; font-style:italic; font-size:0.9rem; }
.metric-row { display:flex; gap:1rem; }
.streaming-dot { animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity:0; } }
</style>
""", unsafe_allow_html=True)


# ── 状态初始化 ──────────────────────────────────────────────────

_SID = str(uuid.uuid4())[:8]
for k, v in [("session_id", _SID), ("history_count", 0)]:
    st.session_state.setdefault(k, v)

EXAMPLE_QUESTIONS: dict[str, str] = {
    "职场决策": "我收到两个 offer，一个是大厂螺丝钉但薪资高，一个是创业公司核心岗但风险大，该怎么选？",
    "商业评估": "我想做一款 AI 笔记产品，但市面上已经有很多竞品了，现在入场还有机会吗？",
    "个人困惑": "总觉得自己在重复过日子，每天上班下班刷手机睡觉，不知道这样有什么意义。",
}



# ═══════════════════════════════════════════════════════════════════
#  异步流式处理 + 界面更新
# ═══════════════════════════════════════════════════════════════════

async def _stream_reply(
    question: str,
    ph_analysis,
    ph_rebuttal,
    ph_summary,
    ph_token,
) -> int:
    """流式分析并逐段刷新界面。返回估计 token 数。"""
    config = QiushiConfig.load()
    engine = QiuShiEngine(config=config)

    async with engine:
        full = ""
        async for token in engine.process_stream(
            st.session_state.session_id, question,
        ):
            full += token
            sections = parse_sections(full)

            main = sections.get("main", "")
            rebuttal = sections.get("rebuttal", "")
            summary = sections.get("summary", "")

            if main:
                ph_analysis.markdown(main)
            if rebuttal:
                ph_rebuttal.markdown(rebuttal)
            if summary:
                ph_summary.markdown(summary)

            # 实时 token 估算
            est = max(len(full) // 4, 1)
            ph_token.metric("本次 Token（实时）", f"{est:,}")

        # 最后再更新一次确保完整
        sections = parse_sections(full)
        main = sections.get("main", "")
        rebuttal = sections.get("rebuttal", "")
        summary = sections.get("summary", "")
        if main:
            ph_analysis.markdown(main)
        if rebuttal:
            ph_rebuttal.markdown(rebuttal)
        if summary:
            ph_summary.markdown(summary)

        token_count = max(len(full) // 4, 1)
        ph_token.metric("本次消耗 Token", f"{token_count:,}")
        return token_count


def _run_analysis(question: str) -> None:
    """在同步 Streamlit 上下文中驱动异步流。"""
    st.divider()

    # ── 三段式容器 ──
    with st.container():
        st.markdown('<div class="section-label section-analysis">📋 分析</div>',
                    unsafe_allow_html=True)
        ph_analysis = st.empty()
        ph_analysis.markdown('<span class="placeholder-text">等待分析...</span>',
                             unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="section-label section-rebuttal">🔄 反思</div>',
                    unsafe_allow_html=True)
        ph_rebuttal = st.empty()

    with st.container():
        st.markdown('<div class="section-label section-summary">✅ 总结</div>',
                    unsafe_allow_html=True)
        ph_summary = st.empty()

    # ── 实时 Token ──
    token_col, total_col = st.columns(2)
    with token_col:
        ph_token = st.empty()
        ph_token.metric("本次 Token", "等待中...")
    with total_col:
        st.metric("累计参考", "1,500,000,000", help="求是全体用户累计 Token 估算")

    # ── 执行 ──
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        token_count = loop.run_until_complete(
            _stream_reply(question, ph_analysis, ph_rebuttal, ph_summary, ph_token)
        )
    finally:
        loop.close()

    st.session_state.history_count += 1
    # 清除分析标记，防止 rerun 重复触发
    st.session_state.pop("_run_analysis", None)


# ═══════════════════════════════════════════════════════════════════
#  界面布局
# ═══════════════════════════════════════════════════════════════════

# ── Banner ──
st.markdown("""
<div style="text-align:center;padding:1.8rem 0 0.5rem">
    <h1 style="font-size:2.6rem;margin:0;font-weight:700">🧠 求是</h1>
    <p style="color:#9CA3AF;font-size:1.05rem;margin:0.4rem 0 0">
        不是更快给答案，是帮你想清楚问题
    </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── 示例按钮 ──
cols = st.columns(3)
for i, (label, question) in enumerate(EXAMPLE_QUESTIONS.items()):
    with cols[i]:
        if st.button(label, use_container_width=True, type="tertiary"):
            st.session_state.question_input = question
            st.session_state._run_analysis = True
            st.rerun()

# ── 输入框 ──
q = st.text_input(
    "你在想什么？",
    key="question_input",
    placeholder="输入你的困惑或决策问题...",
    label_visibility="collapsed",
)

col_send, _ = st.columns([1, 6])
with col_send:
    send = st.button("思辨", type="primary", use_container_width=True)

if send and q:
    st.session_state._run_analysis = True
    st.rerun()

# ── 分析执行（需要放在 rerun 之后才能在 button 下方渲染） ──
if st.session_state.pop("_run_analysis", False):
    q = st.session_state.get("question_input", "")
    if q:
        _run_analysis(q)

# ── Footer ──
st.divider()
st.caption("求是 · 以哲学思辨为框架的 AI 思考伙伴")
