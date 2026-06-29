# 求是 CLI 前端全局架构设计方案 (v1.0)

> 设计日期：2026-06-28
> 状态：已定稿，待骨架接口稳定后实施

## 1. 架构总览：三层分离模型

```
┌─────────────────────────────────────────────────────────────────┐
│                    终端展示层 (Presentation)                   │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐  │
│  │WelcomeRenderer│ │ ChatRenderer  │ │Dialectic/Council    │  │
│  │ (静态入口)     │ │ (流式对话)    │ │ (特殊模式渲染器)    │  │
│  └───────────────┘ └───────────────┘ └─────────────────────┘  │
│  职责：纯布局+颜色+逐字动画，不调用任何 Engine/DB 方法        │
│  输入：ViewModel 字典 / 纯数据类 (dataclass)                  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ 数据流（只读）
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   编排调度层 (Orchestration)                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                CLIOrchestrator (单例/上下文)              │  │
│  │  - 终端尺寸检测 (启动时 + 轮询)                          │  │
│  │  - 命令解析 (/help, /dialectic, /council, /note...)     │  │
│  │  - 会话状态管理 (空闲/流式/等待输入/降级)               │  │
│  │  - 模式切换触发 (沉思↔质疑↔笔记)                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  职责：调度 Engine，转换结果为 ViewModel，维护交互状态机      │
│  依赖：engine.py (只调用 process / process_stream)            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ API 调用
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   核心引擎层 (Core / 骨架)                      │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌─────────────┐    │
│  │Engine │ │Analyzer│ │Retriever│ │LLM   │ │PromptBuilder│    │
│  └───────┘ └───────┘ └───────┘ └───────┘ └─────────────┘    │
│  职责：知识检索、prompt组装、LLM调用、流式yield               │
│  约束：不 import 任何 rich / prompt_toolkit / tui 模块        │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 数据流：从输入到渲染的完整路径

```
用户按键
   │
   ▼
1. prompt_toolkit 获取输入 (cli.py 主循环)
   识别是否为斜杠命令 (/help, /dialectic ...)
   │
   ▼
2. CLIOrchestrator.route_command(input_text)
   - 若为 /command → 执行对应 handler
   - 若为普通文本 → 调用 engine.process_stream()
   │
   ▼
3. Engine.process_stream() 逐块 yield：
   {"type": "status", "phase": "retrieving"}
   {"type": "chunk", "content": "..."}
   {"type": "metadata", "persona": "...", ...}
   │
   ▼
4. CLIOrchestrator 消费流，实时转换为 ViewModel：
   {
     "type": "chat",
     "segments": [
       {"text": "结论", "style": "thesis"},
       {"text": "论据", "style": "argument"},
     ],
     "refs": [{"source": "矛盾论", "quote": "..."}]
   }
   │
   ▼
5. ChatRenderer.render(viewmodel)
   - 使用 rich.Live 逐字刷新屏幕
   - 自动应用 LOGIC_STYLES 配色
   - 绘制知识引用装饰框
   │
   ▼
终端输出（用户可见）
```

### 输入框策略（决策记录 2026-06-28）

采用 **方案丙（同步渲染循环，退出提示后独占终端）**：
- 主循环使用 prompt_toolkit 的同步 prompt()
- AI 回复期间，彻底退出 prompt() 调用，由 rich.live.Live 完全接管终端
- 回复结束后，重新进入 prompt() 等待用户输入
- 用户不可在 AI 回复期间提前打字

理由：零异步代码、输入框天然禁用、状态机完全匹配。"思辨需要专注，读完再回应"符合产品气质。

## 3. 状态机：会话交互的 4 种状态

全局状态由 CLIOrchestrator 维护，渲染器根据状态切换界面表现。

```
                    ┌─────────────┐
                    │   IDLE      │  ← 初始状态 / 输出完成
                    │  (等待输入)  │
                    └──────┬──────┘
                           │ 用户输入文本 / 斜杠命令
                           ▼
                    ┌─────────────┐
            ┌───────│  PROCESSING │────────┐
            │       │ (AI 思考/流式)│       │
            │       └─────────────┘       │
            │  (engine yield status)      │ (流式结束)
            ▼                              ▼
     ┌─────────────┐               ┌─────────────┐
     │  RETRIEVING │               │    IDLE     │
     │ (知识检索中) │               │ (等待输入)   │
     └─────────────┘               └─────────────┘
            │
            ▼
     ┌─────────────┐
     │  STREAMING  │
     │ (逐字输出中) │
     └─────────────┘
```

状态切换时的 UI 行为：
- IDLE → PROCESSING：退出 prompt()，底部显示旋转动画
- PROCESSING → RETRIEVING：状态栏显示旋转省略号（LOADING_FRAMES）
- RETRIEVING → STREAMING：清除状态栏，开始逐字渲染
- STREAMING → IDLE：启用 prompt()，光标恢复，思辨换气停顿 0.4 秒

## 4. 目录结构最终态

```
src/qiushi/
├── cli.py                    # 仅保留：main入口 + prompt_toolkit循环 + 调用Orchestrator
├── engine.py                 # 不变（骨架）
├── analyzer.py               # 不变
├── ... (其他核心模块)
│
├── tui/                      # 前端专项目录
│   ├── __init__.py
│   ├── constants.py          # 所有颜色/样式/枚举/加载帧/尺寸常量
│   ├── orchestrator.py       # CLIOrchestrator 类（调度核心）
│   ├── state.py              # SessionState 数据类 + 状态机枚举
│   ├── commands.py           # 斜杠命令注册表 + handler 映射
│   │
│   └── renderers/            # 渲染器集合（纯展示）
│       ├── __init__.py
│       ├── base.py
│       ├── welcome_renderer.py
│       ├── chat_renderer.py
│       ├── dialectic_renderer.py
│       └── council_renderer.py
│
└── __main__.py               # 不变（入口转发）
```

## 5. 全局样式契约

所有颜色、缩进、装饰符必须且仅定义在 `tui/constants.py` 中。

```python
# 1. 品牌色
BRAND_COLORS = {
    "purple": "#7C3AED",
    "teal": "#00D4AA",
    "amber": "#F59E0B",
}

# 2. 逻辑语义样式
LOGIC_STYLES = {
    "thesis": Style(color="#F59E0B", bold=True, italic=True),
    "argument": Style(color="#00D4AA", dim=True),
    "premise": Style(color="grey70"),
    "knowledge_ref": Style(color="grey50", italic=True),
    "system_op": Style(color="#7C3AED", reverse=True),
}

# 3. 尺寸边界
LAYOUT = {
    "welcome_banner_height": 11,
    "command_panel_height": 8,
    "input_line_height": 1,
    "divider_char": "─",
}

# 4. 降级阈值
TERMINAL_BREAKPOINTS = {
    "full": 100,
    "compact": 80,
    "minimal": 60,
}
```

## 6. 斜杠命令扩展机制

采用命令注册表模式取代当前 cli.py 中的 if-else 硬编码。

```python
class CommandRegistry:
    _handlers = {}

    @classmethod
    def register(cls, name: str, handler: Callable):
        cls._handlers[name] = handler

    @classmethod
    def dispatch(cls, name: str, args: list, orchestrator) -> None:
        if name in cls._handlers:
            cls._handlers[name](args, orchestrator)
        else:
            orchestrator.renderer.render_error(f"未知命令: /{name}")
```

## 7. 性能约束

| 指标 | 阈值 |
| :--- | :--- |
| 逐字渲染帧率 | ≥ 30 fps |
| 命令响应延迟 | < 50ms |
| 终端尺寸检测 | 启动时一次性 |
| 内存占用（渲染层） | < 50MB |
| 历史折叠摘要生成 | < 10ms |

## 8. 实现路线图

| 阶段 | PR | 核心产出 | 依赖 |
| :--- | :--- | :--- | :--- |
| **第0周** | PR #0 | 落地 welcome_renderer.py + constants.py 尺寸常量 + 窄屏降级 | 无 |
| **第1周** | PR #1 | 新建 renderers/ 目录 + CLIOrchestrator 骨架，解耦 cli.py | PR #0 |
| **第2周** | PR #2 | 实现 ChatRenderer + 剧场幕布折叠逻辑 | PR #1 |
| **第3周** | PR #3 | 流式呼吸感（Live 逐字 + 状态指示器） | PR #2 |
| **第4周** | PR #4 | 全量替换硬编码颜色为 LOGIC_STYLES + 知识引用装饰框 | PR #1 |
| **第5周** | PR #5 | 交互模式切换（状态机+输入前缀动态变化） | PR #3 |

## 9. 核心理念

> 引擎只负责"思考结果"（纯文本+元数据），Orchestrator 负责"翻译"（转为 ViewModel），Renderer 负责"表演"（渲染到终端）。
