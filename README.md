# AI Tech Radar

一个基于 AI 的科技情报系统：自动收集 AI 一手资讯、分析科技趋势、生成日报并建立长期知识库。

## 功能

- RSS / GitHub 自动采集
- DeepSeek AI 文章分析与趋势分析
- 信息价值 0-10 分评分
- Markdown 日报生成
- SQLite 长期知识库

## 部署环境

面向新用户，按下面的步骤从零部署。

### 环境要求

- Windows / macOS / Linux
- Python 3.12+
- uv（推荐）或 pip
- GitHub CLI `gh`（GitHub 采集需要）
- DeepSeek API Key（可选；不配置时使用 MockProvider 测试流程）

### 安装

```powershell
git clone https://github.com/CHENYUEWU1/AI-Tech-Radar.git
cd AI-Tech-Radar
uv sync
```

不使用 uv 时：

```powershell
python -m pip install -r requirements.txt
```

### 登录与密钥

```powershell
gh auth login
$env:DEEPSEEK_API_KEY = "你的Key"
```

永久写入 Windows 用户环境变量：

```powershell
setx DEEPSEEK_API_KEY "你的Key"
```

## 快速开始

运行完整管线（采集 → 分析 → 评分 → 趋势 → 日报）：

```powershell
uv run python main.py daily
```

也可分步执行：

```powershell
uv run python main.py collect
uv run python main.py analyze
uv run python main.py score
uv run python main.py report
```

日报输出到 `reports/output/`，数据保存在 `data/radar.db`。

## 目录结构

```text
config/                 # 源、关键词、模型、评分、趋势配置
collectors/             # RSS / GitHub 采集器
analyzers/              # DeepSeek 分析、评分、趋势
reports/                # 日报生成与输出
database/               # SQLite 存储与建表 SQL
pipeline/               # 内部流水线
utils/                  # 配置加载与日志
prompts/                # AI Prompt 模板
scripts/                # Windows 自动化脚本
logs/                   # Loguru 日志
tests/                  # pytest 单元测试
```

## 配置

- `config/sources.yaml`：RSS、GitHub 源列表
- `config/keywords.yaml`：高/中/低优先级关键词
- `config/models.yaml`：DeepSeek 模型配置
- `config/scoring.yaml`：评分权重与日报阈值
- `config/trend.yaml`：趋势分析 Prompt
- `config/settings.yaml`：运行参数

## 迭代开发

这个仓库结构适合交给开发者或 AI 助手继续迭代，推荐流程：

1. 先阅读 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)、[docs/PROJECT_BACKUP.md](docs/PROJECT_BACKUP.md)、[docs/opai对话接力.md](docs/opai对话接力.md) 和 `AGENTS.md`
2. 每次只给一个明确任务，例如“给 `reports/markdown_generator.py` 增加某功能”
3. 改完后运行测试：

```powershell
uv run pytest
```

4. 真实验证完整流程：

```powershell
uv run python main.py daily
```

### OpenAI 对话接力

与 OpenAI 对话可以无缝接力迭代：新开对话时，直接把 [docs/opai对话接力.md](docs/opai对话接力.md) 作为启动上下文发过去，再配合 `AGENTS.md`、`docs/USER_MANUAL.md` 和 `docs/PROJECT_BACKUP.md`，不需要重新解释整个项目，即可继续开发、测试和上传。

更多数据源规划见 [docs/DATA_SOURCE_PLAN.md](docs/DATA_SOURCE_PLAN.md)。
