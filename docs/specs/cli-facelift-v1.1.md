# 求是 CLI 前端优化技术规格书 (v1.1)

> 设计日期：2026-06-28
> 对应前端架构文档：`docs/architecture/cli_frontend.md`

## 1. 前置约束（红线）

1. **禁止修改**以下骨架模块：`engine.py`、`analyzer.py`、`prompt_builder.py`、`llm.py`、`retriever.py`、`db.py`、`writer.py`、`identity.py`、`config.py`。
2. **允许修改**的文件范围仅限于：`src/qiushi/cli.py`、`src/qiushi/tui/` 目录下所有文件、`src/qiushi/__main__.py`（仅入口转发）。
3. 所有新增渲染类必须位于 `src/qiushi/tui/renderers/` 目录。
4. 所有颜色/符号常量必须集中定义在 `src/qiushi/tui/constants.py`，禁止在 `cli.py` 或渲染器中硬编码颜色值。

---

## 2. 任务零：Welcome 欢迎页精准落地（入口渲染）

### 2.1 目标
实现启动时的欢迎页面，包含 ASCII Banner、品牌 tagline、三栏命令卡片便当盒、输入提示符。**所有尺寸必须精确匹配标准终端（100列×24行）**，并实现窄屏优雅降级。

### 2.2 终端尺寸与布局分配（固定值）

**基准终端：100 列 × 24 行**

| 区域 | 宽度（列） | 高度（行） | 内容说明 |
| :--- | :--- | :--- | :--- |
| Banner 区域 | 100 | 11 | ASCII 艺术（6行）+ 上 padding（2行）+ 下 padding（1行）+ tagline（1行）+ 下空行（1行） |
| 分割线 | 100 | 1 | `─` 重复 100 次 |
| 三栏便当盒 | 90（居中，左右各 5 列 padding） | 8 | 三块卡片并排，高度固定为 7 行 + 上下各 0.5 行内边距 |
| 分割线 | 100 | 1 | `─` 重复 100 次 |
| 输入区域 | 100 | 1 | `🧠 求是 > _` 提示符，最底部 |
| 底部留白 | 100 | 1 | 预留一行，避免顶底 |

**合计：11 + 1 + 8 + 1 + 1 + 1 = 23 行**（终端 24 行，最后 1 行为系统状态栏保留）

### 2.3 ASCII Banner 字符画（固定）

```
                    ____    ______  _______ __  ______
                   / __ \  /  _/ / / / ___// / / /  _/
                  / / / /  / // / / /\__ \/ /_/ // /
                 / /_/ / _/ // /_/ /___/ / __  // /
                 \___\_\/___/\____//____/_/ /_/___/
```

**渲染要求**：
- 水平居中（基于 100 列）。
- 颜色：使用靛紫（`#7C3AED`）或青色渐变，不强制。
- 上下各留 2 行空行（padding）。

### 2.4 Tagline 文案（固定）

```
以哲学思辨为框架的 AI 思考伙伴  ·  输入问题直接开始
```

**渲染要求**：
- 位于 Banner 下方，水平居中。
- 颜色：灰色（`grey58`）或青绿（`#00D4AA`）。
- 下方空 1 行。

### 2.5 三栏命令卡片规格

三栏并排，整体水平居中（总宽 90 列，左右各留 5 列边距）。

| 卡片 | 宽度（列） | 标题 | 内容（命令列表，每行一个） | 行数 |
| :--- | :--- | :--- | :--- | :--- |
| 左栏（基础） | 28 | `💬 基础` | `/help 帮助` `/new 新对话` `/clear 清屏` `/exit 退出` | 4 |
| 中栏（思辨） | 31 | `🧠 思辨` | `/dialectic 追问链` `/council 辩论` `/depth 分析深度` `/think 显推理` | 4 |
| 右栏（工具） | 31 | `🔧 工具` | `/web 联网搜` `/search 本地搜` `/profile 画像` `/card 卡片` `/note 笔记` | 5 |

**卡片渲染要求**：
- 每张卡片使用 `rich.Panel` 绘制边框，带标题（标题栏颜色：左栏灰、中栏靛紫、右栏青绿）。
- 命令左对齐，命令名称（如 `/help`）使用粗体或高亮色，说明文字（如 `帮助`）使用灰色。
- **命令名称与说明文字之间固定空 2 格**（如 `/help  帮助` 实际为 `/help` + 2空格 + `帮助`）。
- 卡片内命令列表上下居中（垂直 padding 自动补足）。
- 卡片之间间隔 1 列（即左栏 28 列 + 1 列间隔 + 中栏 31 列 + 1 列间隔 + 右栏 31 列 = 92 列，整体居中，左右各 4 列边距）。

### 2.6 窄屏降级策略（强制实现）

| 终端宽度 | 行为 |
| :--- | :--- |
| `>= 100` 列 | 完整三栏布局（基准） |
| `>= 80` 且 `< 100` 列 | **两栏布局**：基础+思辨合并为一栏（宽度自适应），工具独立为第二栏。Banner 不变。命令卡片高度统一调整为 6 行。 |
| `>= 60` 且 `< 80` 列 | **单栏布局（精简）**：命令卡片全部折叠为一行内联文本，格式为 `基础 : /help /new /clear /exit │ 思辨 : /dialectic /council /depth /think │ 工具 : /web /search /profile /card /note`，置于分割线下方，输入区上方。 |
| `< 60` 列 | **极简模式**：隐藏所有命令卡片和内联命令，仅显示 Banner + 分割线 + `🧠 求是 > _` 输入提示。 |

**降级检测时机**：
- 启动时通过 `shutil.get_terminal_size().columns` 获取一次。
- 用户手动调整终端大小时，不强制实时响应（允许重启生效）。

### 2.7 输入区域规格

**固定显示**：
```
🧠 求是 > _
```

**渲染要求**：
- 位于底部分割线下方一行。
- `🧠 求是 >` 使用靛紫（`#7C3AED`）或品牌色。
- 光标 `_` 使用 `prompt_toolkit` 原生光标，不额外渲染。
- 该行不包含任何额外前缀或装饰，确保用户可直接打字。

### 2.8 实现文件

- 渲染逻辑放置于 `src/qiushi/tui/renderers/welcome_renderer.py`。
- 导出方法：`WelcomeRenderer.render(console: Console, width: int) -> None`。
- `cli.py` 启动时调用 `WelcomeRenderer().render()`，然后进入输入循环。

### 2.9 验收标准

- 在标准 100×24 终端启动 `qiushi`，界面与上述规格逐字符一致（可截图对比）。
- 在 80 列终端启动，自动切换为两栏布局，不出现换行错乱或边框断裂。
- 在 60 列以下终端启动，无任何命令卡片，仅 Banner + 输入框，界面干净无溢出。

---

## 3. 任务一：渲染管线解耦

### 3.1 目标
将 `cli.py` 中所有包含 `rich` 布局、`Panel`、`Columns`、`Live` 的代码段迁移至独立渲染器类，使 `cli.py` 仅保留输入循环与状态机调度。

### 3.2 目录结构变更
```
src/qiushi/tui/renderers/
├── __init__.py
├── base.py
├── welcome_renderer.py      ← 新增（任务零）
├── chat_renderer.py
├── dialectic_renderer.py
└── council_renderer.py
```

### 3.3 基类定义（base.py）
```python
from abc import ABC, abstractmethod
from rich.console import Console

class BaseRenderer(ABC):
    def __init__(self, console: Console):
        self.console = console

    @abstractmethod
    def render(self, data: dict) -> None:
        """接收纯数据字典（POD），执行一次性渲染或启动 Live 循环"""
        pass
```

### 3.4 迁移映射表

| 原 cli.py 函数 | 行号范围 | 目标渲染器文件 | 输入数据字段要求 |
| :--- | :--- | :--- | :--- |
| `_interactive_tui` | 167-314 | `chat_renderer.py::ChatRenderer` | `messages`, `stream_chunks`, `status` |
| `_run_dialectic_tui` | 774-842 | `dialectic_renderer.py::DialecticRenderer` | `rounds`, `current_question`, `user_answers` |
| `_run_council_tui` | 850-907 | `council_renderer.py::CouncilRenderer` | `personae`, `viewpoints`, `consensus` |

### 3.5 验收标准
- `cli.py` 总行数 ≤ 450 行。
- `cli.py` 中 `import rich` 仅允许 `from rich.console import Console`，禁止导入 `Panel`、`Layout`、`Columns` 等布局类。
- 每个 Renderer 必须包含独立的单元测试（位于 `tests/test_tui_renderers.py`），测试时传入 Mock 数据不抛异常。

---

## 4. 任务二：流式输出的"呼吸感"标准化

### 4.1 目标
统一所有 AI 流式输出的渲染速度，并补全"思考中"的状态反馈，消除白屏卡顿。

### 4.2 常量配置（追加至 constants.py）
```python
STREAM_SPEED = {
    "default": 0.025,  # 秒/字符，适配中文阅读
    "fast": 0.008,
    "slow": 0.05,
}

LOADING_FRAMES = ["·", "··", "···", "····"]
LOADING_INTERVAL = 0.3  # 秒
```

### 4.3 渲染实现硬规则
1. **禁止**使用 `print(char, end="", flush=True)` 进行逐字打印。
2. **强制**使用 `rich.live.Live` 配合 `Text` 对象的 `append()` 方法刷新屏幕。
   ```python
   # 伪代码约束
   with Live(console=console, refresh_per_second=30) as live:
       display_text = Text()
       for chunk in stream:
           display_text.append(chunk, style="...")
           live.update(display_text)
   ```
3. 当 `engine.process_stream()` yield 出的状态码为 `"retrieving"` 或 `"metaphoring"` 时，底部状态栏必须显示动态旋转省略号（复用 `LOADING_FRAMES`）。
4. 每当检测到完整句结束（中文标点：`。！？` 或英文 `. ! ?`），强制 `time.sleep(0.4)` 作为"思辨换气"停顿。

### 4.4 验收标准
- 执行 `qiushi chat` 时，字符匀速出现，无明显顿挫或闪屏。
- 在知识检索阶段，终端右下角或底部持续有动态符号，无界面冻结感。

---

## 5. 任务三：视觉层次的"炼金术"映射

### 5.1 目标
建立严格的逻辑语义-终端样式映射表，做到"不看文字，仅看颜色缩进即可辨别结论/论据/引用"。

### 5.2 样式常量（追加至 constants.py）
```python
from rich.style import Style

LOGIC_STYLES = {
    "thesis": Style(color="#F59E0B", bold=True, italic=True),    # 核心结论：琥珀金
    "argument": Style(color="#00D4AA", dim=True),                # 支撑论据：青绿暗色
    "premise": Style(color="grey70"),                            # 前提/引用：灰色
    "knowledge_ref": Style(color="grey50", italic=True),         # 知识库原文
    "system_op": Style(color="#7C3AED", reverse=True),           # 系统指令
}
```

### 5.3 强制替换规则
1. 全局搜索 `cli.py` 和 `tui/*.py` 中所有字符串形式的颜色（如 `"red"`、`"bold white"`、`"#FF0000"`），**全部替换**为 `LOGIC_STYLES` 字典引用。
2. 针对 `retriever.py` 返回的引用文本（知识库摘录），渲染时必须在其上下方添加 Unicode 装饰框：
   ```
   ── 引用自《矛盾论》 ────────
   │  ...原文内容...
   └────────────────────────────
   ```
   装饰框颜色固定为 `grey50`。

### 5.4 验收标准
- 任意问答输出中，结论句必定显示为金色斜体粗体。
- 知识引用块一定带有装饰框，且颜色区别于 AI 生成内容。

---

## 6. 任务四：交互模式的"仪式感"（状态机落地）

### 6.1 目标
通过输入框前缀的动态变化，让用户无感获知当前对话模式（沉思/质疑/笔记）。

### 6.2 枚举定义（追加至 constants.py）
```python
from enum import Enum

class InputMode(Enum):
    CONTEMPLATE = "·"   # 被动阅读
    DEBATE = "?"        # 主动辩论/追问
    EXCERPT = "#"       # 笔记模式
```

### 6.3 实现规范
1. 在 `cli.py` 的输入循环中，维护一个全局状态变量 `current_mode = InputMode.CONTEMPLATE`。
2. 使用 `prompt_toolkit` 的动态 `message` 参数。前缀显示规则：
   - AI 刚结束长输出 → `CONTEMPLATE`（灰色 `·`）
   - 用户输入 `/debate` 或检测到用户消息含"为什么/难道/如果" → 切换为 `DEBATE`（琥珀色闪烁 `?`）
   - 用户输入 `/note` → 切换为 `EXCERPT`（青绿色 `#`）
3. 模式切换时，必须在输入框上方打印一条状态过渡提示（使用 `console.print` 并设置 `highlight=False`）：
   ```text
   [ 沉思 ] → [ 质疑 ]
   ```
   该提示必须使用 `fade` 或自定义 `Live` 控制，**1.2 秒后自动消失**（清除该行）。

### 6.4 验收标准
- 在单次会话中，输入框前缀随对话逻辑自动变色/变符号。
- 模式切换提示不阻塞用户正在输入的文本。

---

## 7. 任务五：长文本的"剧场幕布"滚动逻辑

### 7.1 目标
限制屏幕显示完整对话轮数（最近 3 轮），将历史对话折叠为摘要，避免无限滚动造成的阅读疲劳。

### 7.2 布局比例（强制）
使用 `rich.layout.Layout` 分割终端：
- **可视内容区**：70%（展示当前焦点对话）
- **历史摘要折叠区**：20%（可滚动摘要列表）
- **输入区**：10%（最底部，固定）

### 7.3 折叠实现规则
1. 每当新一轮 AI 回复开始，立即捕获上一轮对话：
   - 调用 `analyzer.py` 中的 `extract_summary` 函数（若该函数不存在，则截取上一轮用户问题或 AI 回复的前 20 个字符）。
   - 将摘要渲染为一行 `< 上一轮思辨摘要：{summary_text} ... >`，存入折叠区。
2. 内容区视口锁定：
   - 使用 `rich.live` 自行管理渲染内容，**禁用**终端原生滚动条（设置 `scrollbar=False`）。
   - 只保留最近 3 轮完整问答在可视内容区，第 4 轮及之前的对话全部转为折叠摘要。
3. 快捷键支持：
   - 按下 `Ctrl + ↑` 时，临时全量展开历史对话（仅作应急查看）。
   - 松开或 3 秒无操作后，自动重新折叠。

### 7.4 验收标准
- 持续对话 20 轮后，终端首屏依然显示最近 3 轮对话，上方为折叠摘要，视线无需上下移动。
- `Ctrl + ↑` 可正常临时展开历史。

---

## 8. 开发执行顺序（强制）

请严格按照以下 PR 顺序提交代码，禁止跨任务合并：

1. **PR #0**：执行任务零（Welcome 欢迎页）— 独立入口，最先落地，建立终端尺寸检测机制。
2. **PR #1**：执行任务一（解耦）— 最底层重构，风险最高，优先合并。
3. **PR #2**：执行任务五（布局重构）— 依赖任务一的渲染器框架。
4. **PR #3**：执行任务二（流式呼吸）— 依赖任务二的 Live 循环结构。
5. **PR #4**：执行任务三（配色映射）— 纯样式替换，依赖任务一的常量位置。
6. **PR #5**：执行任务四（交互仪式）— 最上层交互，最后实施。

---

## 9. 附录：禁止事项清单

- 禁止在渲染器中实例化 `QiuShiEngine` 或任何 `*Manager` 类。
- 禁止使用 `os.system('clear')` 或 `cls` 清屏（破坏终端历史缓冲区）。
- 禁止引入新的第三方依赖（如 `curses`、`urwid`），仅允许使用已有的 `rich` 和 `prompt_toolkit`。
- 禁止在 `constants.py` 外定义任何新的枚举或配置字典。
- 禁止修改 `__main__.py` 的入口转发逻辑，仅允许在 `cli.py` 中调用 `WelcomeRenderer`。
