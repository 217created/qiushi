# 贡献指南

## 开发环境设置

```bash
git clone https://github.com/jianghaowen/qiushi
cd qiushi
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,test]"
```

## 开发流程

1. 创建功能分支：`git checkout -b feat/my-feature`
2. 修改代码
3. 运行测试：`python -m pytest tests/ -v`
4. 提交 PR

## 适合新贡献者的任务

### 1. 增加更多比喻

比喻定义在 `style/features.json` 的 `metaphors` 数组中。每条比喻包含：

```json
{
  "trigger": "触发词",
  "target": "目标词",
  "full": "完整比喻句",
  "scenario": ["general"]
}
```

添加时注意不要重复已有触发词。目前有 60 条，目标 100 条。

### 2. 补充知识库

`knowledge/` 目录按流派分目录。每篇 Markdown 文件包含：

```markdown
# 标题

> 原文精华引用

**如何用在生活中**：现代场景的应用指引（约 100 字）
```

新增内容后同时更新 `_connections.json`，建立新旧知识的关系索引。

### 3. 增加测试用例

测试在 `tests/` 目录下，使用 pytest + pytest-asyncio。核心路径包括：

- 引擎初始化
- 强制三段式解析
- 概念炼金术触发
- 知识检索
- 配置序列化

## 代码风格

- 使用 `black` 格式化（行宽 88）
- 公共方法需要类型注解
- 新增模块需要对应测试

## PR 流程

1. 确保所有已有测试通过
2. 新增功能需要附带测试
3. 提交 PR 后在 PR 描述中说明改动内容和验证方式
