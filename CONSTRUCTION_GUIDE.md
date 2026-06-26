# qiushi TUI 施工规范

## 总纲

本规范定义 qiushi 项目 TUI 界面优化的施工标准。每项改动必须同时考虑 **用户体验 + 代码质量 + 可维护性**。

---

## 一、MyAgentAI 规划与路径决策

### 1.1 项目全景定位

```
MyAgentAI                 ← 编排层 + 入口（p0级）
  ├── 路由 + 多 Agent 协作
  ├── CLI/TUI（app/cli_tui.py）
  ├── FastAPI Web Server
  └── 决策仓库
qiushi                    ← 独立思辨引擎（独立包，p0级）
  ├── 哲学思辨引擎（engine/llm）
  ├── TUI 交互（src/qiushi/cli.py + tui/）
  └── 辩证/辩论模式
▸ 集成关系：MyAgentAI TUI 通过 /qiushi 调用 qiushi（子进程或引擎模式）
```

### 1.2 决策原则

| 维度 | 原则 |
|------|------|
| **架构** | qiushi 保持独立 pip installable，MyAgentAI 为编排层，不耦合 |
| **TUI 定位** | 交互式命令行是第一入口，Web Server 为集成接口 |
| **代码边界** | 不改动核心引擎（engine/llm/dialectic/council），只改 TUI 展示层 |
| **可测试性** | 渲染逻辑应与业务逻辑分离，渲染函数可单独调用 |

### 1.3 路径优先级

```
P0（必须）→ P1（重要）→ P2（增强）→ P3（体验）
每个 P 必须完成后才进入下一个，不允许跳跃。
```

---

## 二、施工细则

### 2.1 通用规范

| 规则 | 内容 |
|------|------|
| **一次性完成** | 不允许分批审查。当前 P 所有改动一次性交付，然后进入下一个 P |
| **零断裂** | 每项改动必须在实际环境中验证通过，不能出现语法错误或导入断裂 |
| **改动范围** | 只改 `qiushi/src/qiushi/tui/` 和 `qiushi/src/qiushi/cli.py` 的展示逻辑。核心引擎 `engine.py`、`llm.py`、`dialectic.py`、`council.py` 不动 |
| **终端自适应** | 所有展示逻辑必须考虑 `tw < 50`（超窄）、`50-80`（窄）、`80-120`（宽）、`120+`（超宽）四种场景 |
| **中文字符** | emoji + 中文混合排版需校验对齐，Rich Panel/Table 的 border 不能因为中文宽字符错位 |
| **测试方式** | 修改后 `cd ~/qiushi && python -c "from qiushi.tui.xxx import *; print('OK')"` 验证导入 |
| **提交方式** | 每个 P 完成并且验证通过后交付，不需要等全部做完才交付 |

### 2.2 代码质量控制

1. **函数职责**：每个函数只做一个事情，渲染函数不做业务逻辑
2. **宽屏优先**：先写好宽屏版，再向下兼容窄屏（"窄屏无损"是底线）
3. **常量复用**：品牌色/loading文案等从 `tui/constants.py` 导入，不硬编码
4. **禁止引入复杂依赖**：不新增 `matplotlib`/`pillow` 等重型包
5. **错误处理**：加载失败/API超时等情况，用友好的 Panel/提示，不抛裸异常

### 2.3 TUI 设计原则

```
用户进入 TUI 的路径：
  qiushi chat（或直接 qiushi）
    → 首页（_show_home）
    → 输入提示符 "❯ "
    → 输入命令或自由对话
    → 输出结果（Panel/Markdown）
```

#### 首页规范
- 窄屏显示极简版（2-3 行），宽屏显示完整版
- 首次进入要有清晰的新手指引
- 命令分组要合理：思辨 / 知识 / 会话控制

#### 对话流程规范
- 输入提示符清晰可见
- 状态栏（bottom_toolbar）显示深度/模式/对话条数
- 输出结果用 Panel 包装，subtitle 标注来源
- 长文本自动 Markdown 渲染，代码块限制宽度

#### 命令处理规范
- `/help` 显示全部命令，自适应宽度
- `/new` + `/clear` 不丢用户状态
- `/exit` / `/quit` / `/back` 明确返回路径
- 未知命令显示友好提示 + /help 指引

### 2.4 安全红线

| ❌ 禁止 | ✅ 替代 |
|---------|---------|
| 修改 engine.py/llm.py/dialectic.py/council.py | 只改 tui/ 和 cli.py 展示层 |
| 引入新的重型 Python 包 | 用已有的 rich/prompt_toolkit |
| 破坏窄屏 `tw<60` 的可用性 | 每项改动必须在窄屏验证 |
| 造成语法错误 / import 断裂 | py_compile.compile() 验证 |
| 硬编码 magic number | 统一放到 constants.py |
| 删除现有功能 | 只增强/补充，不删减 |
| 改动后不测试 | 必须 `python -c "import..."` + 实际运行至少一次 |
| 分包修改、分多次交付 | 单次完成一个 P 的全部改动 |

---

## 三、P0-P3 执行计划

### P0 — 基础体验（终端自适应 + 窄屏无损）

目标：解决窄屏 `<80` 下所有布局溢出、截断、信息丢失问题。

改动文件：
- `tui/constants.py`：窄屏版的 BANNER_ASCII/HELP_TEXT
- `cli.py`：`_show_home` 窄屏版缺少常用命令；`_handle_slash_command` 中 /help 窄屏显示优化
- `tui/council_renderer.py`：窄屏布局缺少 personas_panel 改名问题
- `tui/dialectic_renderer.py`：窄屏 padding 统一

### P1 — 交互提示（状态栏+反馈增强）

目标：让用户在操作中始终知道"我在哪"、"能做什么"、"正在做什么"。

改动文件：
- `cli.py`：状态栏显示更多上下文，加载中的提示更具体
- `tui/constants.py`：补充 loading phases

### P2 — 输出美观（结构展示优化）

目标：长回复不刷屏，辩论/辩证结果结构清晰。

改动文件：
- `tui/council_renderer.py`：辩论结果展示优化
- `tui/dialectic_renderer.py`：追问链展示优化

### P3 — 细节体验（微交互打磨）

目标：让 TUI 使用起来更"顺手"。

改动文件：
- `cli.py`：细节优化（记忆上次深度、命令别名等）
- `tui/constants.py`：help 文本优化
