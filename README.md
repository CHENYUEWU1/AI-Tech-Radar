# AI Tech Radar

一个基于 AI 的科技情报系统：自动收集 AI 一手资讯、分析科技趋势、生成日报并建立长期知识库。

## 技术栈

- Python 3.12+
- uv
- SQLite
- YAML
- Loguru

## 快速开始

```powershell
uv sync
uv run python main.py
```

`main.py` 会读取并格式化打印 `config/sources.yaml` 和 `config/keywords.yaml`。

完整采集、分析、日报管线：

```powershell
uv run python -m ai_tech_radar run --sources rss,github --limit 20
```

也可分步执行：

```powershell
uv run python -m ai_tech_radar collect --sources github
uv run python -m ai_tech_radar analyze --limit 200
uv run python -m ai_tech_radar report --date 2026-07-31
```

X/Twitter 采集需要官方 Bearer Token，配置环境变量 `X_BEARER_TOKEN` 后会自动启用；GitHub 可选用 `GITHUB_TOKEN` 提升速率限制。

## 目录结构

```text
config/                 # 源、关键词、运行设置
collectors/             # RSS / GitHub / X 采集器
analyzers/              # 关键词打分与趋势聚合
reporters/              # Markdown 日报生成
database/               # SQLite 存储层
reports/                # 生成的日报
logs/                   # Loguru 日志
tests/                  # pytest 单元测试
```

## 配置

- `config/sources.yaml`：RSS、GitHub、X 源列表
- `config/keywords.yaml`：高/中/低优先级关键词
- `config/settings.yaml`：数据库、报告、日志、采集参数
