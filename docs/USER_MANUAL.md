# AI-Tech-Radar 用户手册

AI-Tech-Radar 是一个 AI 科技情报系统：自动采集 AI 相关新闻和开源项目，使用 DeepSeek 做文章分析、信息价值评分、趋势分析，并生成 Markdown 日报。

## 环境要求

- Windows / macOS / Linux
- Python 3.12+
- uv（推荐）或 pip
- GitHub CLI `gh`（GitHub 采集需要，且已登录）
- DeepSeek API Key（用于真实 AI 分析）

## 快速开始

```powershell
cd AI-Tech-Radar
uv sync
uv run python main.py daily
```

如果不使用 uv：

```powershell
python -m pip install -r requirements.txt
python main.py daily
```

首次运行会自动：

1. 读取 `config/`
2. 初始化 `data/radar.db`
3. 创建 `articles`、`analysis_results`、`importance_scores` 表
4. 采集 RSS 和 GitHub 数据
5. 分析 20 篇文章（每个类别最多 3 篇）
6. 对文章做 0-10 分价值评分
7. 分析趋势
8. 生成日报

## API Key 配置

DeepSeek Key 通过环境变量读取，不写入代码和配置文件：

```powershell
$env:DEEPSEEK_API_KEY = "你的Key"
```

也可以永久配置到 Windows 用户环境变量：

```powershell
setx DEEPSEEK_API_KEY "你的Key"
```

没有配置 Key 时，系统会使用 `MockProvider`，可以测试流程，但不会生成真实 AI 内容。

GitHub 采集使用 `gh` 已登录账号：

```powershell
gh auth login
gh auth status
```

## 命令说明

```powershell
python main.py collect    # 只执行 RSS + GitHub 采集
python main.py analyze    # 只执行 AI 文章分析
python main.py score      # 只执行信息价值评分
python main.py report     # 只生成日报
python main.py daily      # 执行完整流程
python main.py            # 等价于 daily
```

## 目录结构

```text
AI-Tech-Radar/
├── main.py                     # CLI 入口，负责流程编排
├── pyproject.toml              # uv / Python 项目配置
├── requirements.txt            # 简化依赖清单
├── AGENTS.md                   # AI 协作规范
├── config/                     # 所有配置文件
│   ├── sources.yaml            # RSS / GitHub 数据源
│   ├── keywords.yaml           # 高/中/低优先级关键词
│   ├── models.yaml             # DeepSeek 模型参数
│   ├── scoring.yaml            # 评分权重和日报阈值
│   └── trend.yaml              # 趋势分析 Prompt 配置
├── collectors/                 # 数据采集器
│   ├── rss_collector.py        # RSS/Atom 采集
│   └── github_collector.py     # GitHub 仓库采集
├── analyzers/                  # AI 分析层
│   ├── provider.py             # AIProvider 抽象接口
│   ├── deepseek_provider.py    # DeepSeek 实现
│   ├── mock_provider.py        # 测试用 Mock Provider
│   ├── analyzer.py             # AIAnalyzer 协调层
│   ├── schemas.py              # AnalysisResult 数据结构
│   ├── importance_scorer.py    # 信息价值评分
│   └── trend_analyzer.py       # 趋势分析
├── database/                   # SQLite 数据层
│   ├── storage.py              # 文章表读写
│   ├── analysis_repository.py  # 文章分析结果存取
│   ├── importance_repository.py# 评分结果存取
│   ├── analysis_schema.sql     # analysis_results 建表
│   └── importance_schema.sql   # importance_scores 建表
├── reports/                    # 日报层
│   ├── data_aggregator.py      # 查询高分文章和原文摘录
│   ├── markdown_generator.py   # Markdown 日报生成
│   └── report_pipeline.py      # 日报流程编排
├── pipeline/                   # 内部流水线
│   └── analyzer_pipeline.py    # 单篇文章分析 + 保存
├── utils/                      # 通用工具
│   ├── config_loader.py        # YAML 配置加载
│   └── logger.py               # Loguru 日志系统
├── prompts/                    # Prompt 模板
│   ├── ai_analysis.yaml        # 文章分析 Prompt
│   └── daily_report.yaml       # 日报生成 Prompt
├── scripts/                    # 自动化脚本
│   ├── run_daily.bat           # Windows 定时运行
│   └── README.md               # 任务计划配置说明
├── tests/                      # pytest 测试
├── data/radar.db               # SQLite 数据库（自动生成）
├── logs/                       # 日志（自动生成）
└── reports/output/             # 日报输出（自动生成）
```

## 主要文件职责

| 文件 | 职责 |
| --- | --- |
| `main.py` | 参数解析、流程调度、日志输出 |
| `collectors/rss_collector.py` | 并发抓取 RSS，归一化为统一条目 |
| `collectors/github_collector.py` | 通过 `gh` 拉取 GitHub 仓库并按关键词过滤 |
| `analyzers/deepseek_provider.py` | 调用 DeepSeek API，解析 JSON |
| `analyzers/importance_scorer.py` | 按权重输出 0-10 信息价值评分 |
| `analyzers/trend_analyzer.py` | 分析国内外趋势、信息差和机会 |
| `database/storage.py` | 保存文章，查询未分析/未评分文章 |
| `reports/data_aggregator.py` | 只取 `importance_score >= 7` 的文章 |
| `reports/markdown_generator.py` | 生成 Markdown 日报，时间戳命名 |
| `utils/logger.py` | 控制台 + `logs/app.log` + `logs/error.log` |

## 配置说明

### `config/sources.yaml`

定义采集源：

- `rss`：RSS/Atom 源
- `github`：GitHub 组织或仓库
- `github_keywords`：GitHub 仓库过滤关键词

每个 RSS 源支持：

```yaml
- name: OpenAI Blog
  category: ai_company
  url: https://openai.com/news/rss.xml
  enabled: true
```

### `config/keywords.yaml`

定义高/中/低优先级关键词，例如：

```yaml
high_priority:
  - Agent
  - MCP
  - LLM
  - GPU
  - 长鑫
  - 芯片
  - 股票
```

### `config/models.yaml`

DeepSeek 模型配置：

```yaml
ai:
  provider: deepseek
  model:
    name: deepseek-chat
  api:
    key_env: DEEPSEEK_API_KEY
  parameters:
    temperature: 0.2
    max_tokens: 8000
```

### `config/scoring.yaml`

评分权重和日报阈值：

```yaml
weights:
  technical_impact: 0.3
  information_scarcity: 0.2
  industry_impact: 0.25
  trend_value: 0.15
  source_credibility: 0.1

max_score: 10
daily_min_score: 7
```

日报和趋势分析只使用 `importance_score >= 7` 的文章。

## 数据流

```text
collection
  ↓
analysis
  ↓
scoring
  ↓
trend analysis
  ↓
report
```

## 数据库表

### `articles`

采集到的原始文章：

- `external_id`：唯一标识
- `source`：来源名称
- `category`：类别
- `title` / `link` / `summary` / `content`
- `author` / `published_at` / `created_at`

### `analysis_results`

AI 文章分析结果：

- `article_id`：关联 `articles.id`
- `importance` / `category` / `tags`
- `summary` / `impact` / `action`
- `model` / `created_at`

### `importance_scores`

信息价值评分：

- `article_id`：关联 `articles.id`
- `importance_score`：0-10
- `impact` / `reason` / `trend`
- `model` / `created_at`

## 日报输出

日报保存到：

```text
reports/output/YYYY-MM-DD-时间戳-ai-tech-radar.md
```

每次生成新文件，不会覆盖旧日报。

## 日志

- `logs/app.log`：INFO 级别日志
- `logs/error.log`：ERROR 级别日志
- `logs/daily_console.log`：批处理运行日志

## 自动化

Windows 任务计划程序配置：

```text
程序或脚本: C:\AI-Tech-Radar\scripts\run_daily.bat
起始于: C:\AI-Tech-Radar
```

详见 `scripts/README.md`。

## 测试

```powershell
uv run pytest
```

或者：

```powershell
.venv\Scripts\python.exe -m pytest
```

当前全量测试：

```text
112 passed
```

## 如何让 AI 继续迭代

这个仓库结构适合交给任何 AI 助手继续开发。推荐做法：

1. 给 AI 提供：
   - 本手册 `docs/USER_MANUAL.md`
   - `AGENTS.md`
   - 相关模块源码
2. 每次只给一个明确任务，例如：
   - “给 `reports/markdown_generator.py` 增加某功能”
   - “新增一个数据源”
   - “修复某个报错”
3. 要求 AI 改完后运行：

```powershell
uv run pytest
```

4. 真实验证：

```powershell
uv run python main.py daily
```

## 注意事项

- 不要在任何配置或代码里写入真实 API Key
- RSS 源可能偶尔超时，单个源失败不会中断整体流程
- 完整 `daily` 会调用大量 DeepSeek API，运行时间约 1-2 分钟
- X/Twitter 配置已预留，但当前主流程未启用 X 采集
- 日报只读取 `importance_score >= 7` 的文章
