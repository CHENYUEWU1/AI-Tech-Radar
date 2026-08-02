# AI-Tech-Radar 项目交接备份

> 本文件用于保存项目到目前为止的完整上下文，方便新对话或新协作者快速接手。
> 新对话建议先读取：
> 1. `AGENTS.md`
> 2. `docs/USER_MANUAL.md`
> 3. `docs/PROJECT_BACKUP.md`

## 1. 项目简介

AI-Tech-Radar 是一个 AI 科技情报系统，用于：

- 自动采集 AI 一手资讯和开源项目
- 使用 DeepSeek 分析文章
- 对文章做 0-10 分信息价值评分
- 分析国内外趋势和信息差
- 生成 Markdown 日报
- 建立长期本地知识库

技术栈：

- Python 3.12+
- uv
- SQLite
- YAML
- Loguru
- requests
- GitHub CLI `gh`
- DeepSeek API

## 2. 当前状态

截至 2026-08-01：

- 全量测试：`112 passed`
- 完整 `daily` 流程已真实跑通
- 一次真实 daily 结果：
  - RSS 采集：263 条
  - GitHub 采集：307 条
  - 共保存：570 条
  - AI 分析：20/20 成功
  - 价值评分：20/20 成功
  - 高分文章（>=7）：2 篇
  - 趋势分析：2 条趋势
  - 日报生成成功

## 3. 任务历史

| 任务 | 内容 | 状态 |
| --- | --- | --- |
| Task001 | Configuration Loader | 完成 |
| Task002 | RSS Collector | 完成 |
| Task003 | SQLite Storage | 完成 |
| Task004-A | AI Analyzer 基础结构 | 完成 |
| Task004-B1 | AI Provider 抽象接口 | 完成 |
| Task004-B2 | Mock AI Provider | 完成 |
| Task004-C | AI Analyzer Orchestrator | 完成 |
| Task004-D | AI Pipeline Integration Test | 完成 |
| Task004-E1 | AI 模型配置 models.yaml | 完成 |
| Task004-E2-A | DeepSeek Provider 骨架 | 完成 |
| Task004-E2-B1 | DeepSeek API Client | 完成 |
| Task004-E2-B2 | DeepSeek Structured Output Parser | 完成 |
| Task004-F1 | AI Analysis 数据库设计 | 完成 |
| Task004-F3 | Analyzer Pipeline | 完成 |
| Task005-A | Report Data Aggregator | 完成 |
| Task005-B | Daily Report Prompt | 完成 |
| Task005-C | Markdown Report Generator | 完成 |
| Task005-D | Report Pipeline | 完成 |
| Task006-A | Application Bootstrap | 完成 |
| Task006-B0.5 | SQLite 初始化验证 | 完成 |
| Task006-B1 | RSS Runtime Integration | 完成 |
| Task006-B1.1 | Article Persistence 修复 | 完成 |
| Task006-B2 | AI Analyzer Runtime Integration | 完成 |
| Task006-B3 | Report Runtime Integration | 完成 |
| Task007 | CLI Command Interface | 完成 |
| Task008-A | Logging System Upgrade | 完成 |
| Task008-B | Windows 自动运行准备 | 完成 |
| Task009-A | GitHub Collector | 完成 |
| Task009-B | AI Analyzer Reliability | 完成 |
| Task010 | AI Intelligence Scoring System | 完成 |
| Task011 | Trend Intelligence Analyzer | 完成 |
| Task012 | Twitter Collector（X v2 API） | 完成 |

## 4. 核心架构

```text
main.py
  ↓
Config
  ↓
Database
  ↓
Collectors
  ↓
Analyzers
  ↓
Scoring
  ↓
Trend Analysis
  ↓
Report
```

### 数据流

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

### CLI 命令

```powershell
python main.py collect    # RSS + GitHub 采集
python main.py analyze    # AI 分析，20 篇，每类最多 3 篇
python main.py score      # 信息价值评分
python main.py report     # 生成日报
python main.py daily      # 完整流程
```

## 5. 关键设计决策

### 5.1 目录采用根目录模块

当前 `main.py` 使用根目录模块：

- `collectors/`
- `analyzers/`
- `database/`
- `reports/`
- `pipeline/`
- `utils/`
- `prompts/`

`src/ai_tech_radar/` 是早期遗留实现，当前主流程不使用。

### 5.2 RSS 采集

- 并发采集，`MAX_WORKERS=4`
- 默认超时 `8 秒`
- 单源失败只记录日志，不中断
- 输出统一为 `RSSItem`

### 5.3 GitHub 采集

- 使用 `gh api`
- 组织仓库只取最近更新的前 100 个，不使用 `--paginate`
- 默认超时 `30 秒`
- 子进程使用 `encoding="utf-8", errors="replace"`
- 按 `github_keywords` 过滤

### 5.4 AI 分析

- `DeepSeekProvider` 会加载 `prompts/ai_analysis.yaml`
- 请求包含 system prompt
- 支持普通 JSON、` ```json ` 代码块、前后带文本的 JSON
- 解析失败直接跳过，不重试
- `analyze()` 返回 `AnalysisResult`
- 额外提供 `complete()` 返回原始文本，供趋势分析使用

### 5.5 价值评分

- `ImportanceScorer` 使用 `config/scoring.yaml`
- 评分范围 0-10
- 权重维度：
  - technical_impact
  - information_scarcity
  - industry_impact
  - trend_value
  - source_credibility
- 权重之和必须约等于 1.0

### 5.6 趋势分析

- `TrendAnalyzer` 使用 `config/trend.yaml`
- 输入：`importance_score >= 7` 的文章
- 输出字段：
  - major_trends
  - domestic_analysis
  - global_analysis
  - information_gap
  - future_prediction
  - opportunities
- 使用 `DeepSeekProvider.complete()` 获取原始趋势 JSON

### 5.7 日报

- 只使用 `importance_score >= 7` 的文章
- 默认 `min_score=7` 已下沉到：
  - `ReportDataAggregator`
  - `ReportPipeline`
- 日报文件使用时间戳 + 随机后缀命名，不覆盖旧文件（避免 Windows 时钟分辨率导致的同名）
- 日报 Prompt 要求：
  - 每条重点带原文链接和发布时间
  - 按主题/类别分组，每个主题精选 3 篇
  - 不硬性按地域切分开源/模型/社区项目
  - 方向判断覆盖开源 vs 闭源、存储供给、安全治理、资本风险、监管动态

### 5.8 Twitter 采集

- 两种模式：
  - 官方 X v2 API：`X_BEARER_TOKEN`，批量解析用户 ID（`users/by`）再按账号拉取，默认每账号 20 条，排除转推和回复
  - RSSHub RSS 兜底：无 Token 时自动启用，`RSSHUB_BASE_URL` 可指定实例（逗号分隔多个），默认 `https://rsshub.app`
- 两种方式都不可用时告警跳过，不影响 RSS / GitHub 流程

## 6. 文件地图

详细说明见 `docs/USER_MANUAL.md`。

```text
main.py                             # CLI 入口
config/                             # 所有配置
collectors/                         # RSS / GitHub
analyzers/                          # Provider / 分析 / 评分 / 趋势
database/                           # SQLite 存储和 Repository
reports/                            # 日报聚合、生成、流水线
pipeline/                           # 内部流水线
utils/                              # 配置加载和日志
prompts/                            # AI Prompt
scripts/                            # Windows 定时脚本
tests/                              # pytest
docs/                               # 规划、手册、交接备份
```

## 7. 数据库

数据库文件：

```text
data/radar.db
```

### articles

采集到的文章。

### analysis_results

AI 文章分析结果。

### importance_scores

信息价值评分，`importance_score` 范围 0-10。

## 8. 配置

- `config/sources.yaml`：数据源
- `config/keywords.yaml`：关键词优先级
- `config/models.yaml`：DeepSeek 模型参数
- `config/scoring.yaml`：评分权重和阈值
- `config/trend.yaml`：趋势分析配置
- `config/settings.yaml`：保留配置，当前主流程未强制依赖

## 9. 环境变量

```text
DEEPSEEK_API_KEY
```

GitHub 使用：

```powershell
gh auth login
```

## 10. 已知问题

- 部分 RSS 源偶尔超时或 404，已做单源容错
- Reddit 有时返回 429
- X/Twitter 采集已接入，官方 API 需验证开发者账户；无 Token 时走 RSSHub 兜底（公共实例 Twitter 路由目前不稳定，建议自建）
- 完整 daily 需要大量 DeepSeek API 调用，耗时约 1-2 分钟
- `src/ai_tech_radar/` 是遗留代码，后续可以清理或合并

## 11. 后续建议

- 增加 OpenAI / Claude Provider
- 增加 OpenAI / Claude Provider（已接入 X 采集）
- 增加日报已用文章去重，避免重复
- GitHub 采集并发化
- 增加 Web UI 或 API
- 增加数据库备份机制
- 清理 `src/` 遗留代码
- 增加 CI

## 12. 新对话接手提示

推荐给新 AI 的启动提示：

```text
请先阅读 C:\AI-Tech-Radar\AGENTS.md，
然后阅读 C:\AI-Tech-Radar\docs\USER_MANUAL.md，
最后阅读 C:\AI-Tech-Radar\docs\PROJECT_BACKUP.md。

当前项目是一个 AI 科技情报系统。
请确认项目结构和当前状态后，再继续处理我的任务。
```

新对话可以先运行：

```powershell
uv run pytest
uv run python main.py daily
```
