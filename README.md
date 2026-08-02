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

## 两个程序：AI Tech Radar 与科技信息差采集工具

本仓库现在包含**两个可独立运行的程序**，按分工互补，不互相冲突：

| 程序 | 位置 | 职责 |
| --- | --- | --- |
| AI Tech Radar（主程序） | `main.py` | 模型侧：模型发布/跑分、开源 vs 闭源、推理引擎与本地部署、模型定价、AI 数学/科研突破；评分、趋势、知识库、日报 |
| 科技信息差采集工具 | `tools/tech-info-gap/collect.py` | 其余所有第一手/多渠道：芯片存储算力、AI 安全事件、政策监管、公司财报与资本、消费电子/汽车/机器人、硬科技前沿（也会顺带抓模型侧条目作为提示） |

### 运行方法

**① AI Tech Radar（完整管线：采集 → 分析 → 评分 → 趋势 → 日报）**

```powershell
cd C:\AI-Tech-Radar
uv run python main.py daily
```

也可分步：`uv run python main.py collect / analyze / score / report`。

**② 科技信息差采集工具（多渠道一键采集）**

```powershell
python C:\AI-Tech-Radar\tools\tech-info-gap\collect.py
```

常用参数：`--hours 12`（时间窗口）、`--no-fetch`（复用缓存不重抓）、`--out`（自定义输出路径）。详细说明见 [tools/tech-info-gap/README.md](tools/tech-info-gap/README.md)。

### 会不会冲突？

**结论：不会互相覆盖，可并行运行。** 原因如下：

1. **报告输出同名不同**：两个程序都写 `reports/output/`，但文件名互不重叠——
   - Radar 日报：`YYYY-MM-DD-<时间戳>-ai-tech-radar.md`
   - 采集工具报告：`YYYY-MM-DD.md`
   - 合并简报：`YYYY-MM-DD-科技信息差-合并简报.md`
2. **配置互不影响**：Radar 读取 `config/*.yaml`（`sources.yaml` / `keywords.yaml` 等）；采集工具内置自己的源列表（`collect.py` 顶部字典），不读 Radar 的配置文件，两边怎么改都不会互相破坏。
3. **数据层隔离**：Radar 写 `data/radar.db` 知识库；采集工具只写 Markdown 报告和 `cache/` 缓存。
4. **唯一共享资源是网络限流**：同时跑时，GitHub `gh` 与 X/nitter 的请求频率会互相挤占（可能变慢或被 429），建议错开 1~2 分钟，不影响结果。
5. **内容互补而非重复**：模型侧细节归 Radar，其余板块归采集工具；交叉新闻（如 DeepSeek 发布 + 硬件门槛 + 市场影响）由整理方按分工拆分，一份报告只保留对应侧内容。

### 今日结果示例（2026-08-02）

- AI Tech Radar 日报（上午）：[2026-08-02-093511-044989-ai-tech-radar.md](reports/output/2026-08-02-20260802-093511-044989-ai-tech-radar.md)
- AI Tech Radar 日报（中午重跑）：[2026-08-02-104455-765320-fb9546c4-ai-tech-radar.md](reports/output/2026-08-02-20260802-104455-765320-fb9546c4-ai-tech-radar.md)
- 科技信息差多渠道采集报告：[2026-08-02.md](reports/output/2026-08-02.md)
- 科技信息差合并简报（Radar + 多渠道结合）：[2026-08-02-科技信息差-合并简报.md](reports/output/2026-08-02-科技信息差-合并简报.md)

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
tools/tech-info-gap/    # 科技信息差采集工具（独立程序，见下方说明）
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

> 注：`tools/tech-info-gap/collect.py` 的渠道清单维护在脚本顶部（`DOMESTIC_FEEDS`、`X_ACCOUNTS`、`BLOG_FEEDS`、`YOUTUBE_FEEDS` 等字典），与 `config/sources.yaml` 相互独立。

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
