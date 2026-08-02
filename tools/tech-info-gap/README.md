# 科技信息差采集工具（Codex 侧）

对应分工：AI Tech Radar 负责模型侧；本工具负责其余所有渠道的**第一手/多渠道采集**（芯片存储、安全、政策、资本、消费电子、汽车机器人、科研等），以及模型侧信息的提示性抓取（是否深挖由 Radar 决定）。

## 一条命令拉全

```powershell
python C:\AI-Tech-Radar\tools\tech-info-gap\collect.py
```

默认抓取最近 30 小时，报告输出到 `C:\AI-Tech-Radar\reports\output\YYYY-MM-DD.md`（可与 AI Tech Radar 日报放同一目录）。

## 常用参数

| 参数 | 作用 |
| --- | --- |
| `--hours 12` | 自定义时间窗口（小时） |
| `--out 路径.md` | 指定输出文件 |
| `--report-dir 目录` | 指定输出目录（默认 `C:\AI-Tech-Radar\reports\output`） |
| `--no-fetch` | 不重新抓取，直接用上次缓存生成报告 |

## 覆盖渠道

- **国内媒体**：IT之家、36氪、极客公园、爱范儿、少数派、虎嗅、钛媒体、CnBeta
- **海外媒体/社区**：TechCrunch、Ars Technica、The Register、The Verge、Engadget、Hacker News
- **X/推特（第一手）**：elonmusk、sama、OpenAI、AnthropicAI、ylecun、hwchase17、dhh、gdb、JimFan、deepseek_ai、GoogleDeepMind、AIatMeta、nvidia、karpathy、TheTuringPost、coinbase（经 nitter 镜像，自动多实例重试）
- **官方博客**：OpenAI News、Google AI、Google DeepMind、NVIDIA（Anthropic 无 RSS，走 Newsroom 页面）
- **YouTube**：LTT、Fireship、MKBHD
- **Reddit**：r/technology、r/LocalLLaMA、r/hardware、r/singularity（本环境常被限流，失败会在状态表标出）
- **Bluesky**：关键词搜索（public API，本环境常 403，失败会在状态表标出）

## 输出结构

生成的 Markdown 包含：

1. 抓取状态表（每个源 OK/FAIL + 字节数/错误原因）
2. 按渠道分组的近期条目（标题、来源链接、摘要）

原始抓取缓存存在 `cache\`，便于 `--no-fetch` 复跑。

## 扩展渠道

在 `collect.py` 顶部维护几个字典即可：

- `DOMESTIC_FEEDS` / `INTL_FEEDS`：RSS 源
- `X_ACCOUNTS`：X 账号（value 为 handle）
- `BLOG_FEEDS`：官方博客 RSS
- `YOUTUBE_FEEDS`：YouTube 频道（channel_id）
- `REDDIT_SUBS`、`BLUESKY_QUERIES`：Reddit 子版、Bluesky 关键词

## 已知限制

- Reddit、Bluesky 从本机直连常被 403/429，需换网络、代理或认证后才能补全。
- Meta AI、Microsoft 官方博客会拒绝脚本 UA（403），当前未纳入。
- X 经 nitter 镜像有频率限制，脚本已加 1.5s 间隔；若仍 429 可稍后重跑 `--no-fetch` 之外的完整命令。
- 本工具产出的是**素材清单**，最终"信息差"判断仍由 Codex 按分工筛选整理。
