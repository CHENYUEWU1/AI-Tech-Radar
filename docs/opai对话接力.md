好的，我帮你整理一份新对话启动上下文。下一次直接复制这份即可，不需要重新解释整个项目。



AI-Tech-Radar 项目上下文总结

项目目标



正在开发一个个人 AI 科技情报系统。



目标：



自动获取全球 AI / 科技信息，通过 AI 分析、筛选、趋势判断，生成类似专业科技早报的信息差报告。



最终方向：



类似：



Bloomberg 科技情报

AI 研究员日报

个人科技分析助手

当前项目位置



项目目录：



C:\\AI-Tech-Radar



Python：



Python 3.12



数据库：



C:\\AI-Tech-Radar\\data\\radar.db



数据库为 SQLite。



当前技术架构



目前已经完成：



数据源



↓



Collector采集层



↓



Article统一数据结构



↓



SQLite数据库



↓



AI Analyzer



↓



Importance Scorer



↓



Trend Analyzer



↓



Report生成



↓



Markdown日报

已完成模块

1\. RSS Collector ✅



已经可以采集：



OpenAI Blog

Google DeepMind

Hacker News

Hugging Face

等 RSS



遇到过：



部分 RSS 404：



Anthropic

Meta AI

NVIDIA



属于源地址问题，不影响架构。



2\. Database ✅



数据库：



radar.db



已经正常保存数据。



之前误以为：



ai\_tech\_radar.db



实际项目使用：



data/radar.db

3\. DeepSeek Analyzer ✅



已经接入 DeepSeek。



之前遇到：



DeepSeek content is not valid JSON



原因：



模型返回 Markdown 或非 JSON。



已经修复方向：



强化 JSON parser

限制分析数量

增加错误处理

4\. Report日报生成 ✅



已经解决：



DeepSeek 输出 Markdown 与 JSON要求冲突。



现在日报流程正常。



5\. Importance Scorer 信息价值评分 ✅



新增目标：



不要让 AI 处理所有新闻。



流程：



80篇文章



↓



AI评分



↓



筛选高价值事件



评分维度：



技术影响力

信息稀缺度

行业影响

趋势价值

来源可信度



输出：



{

"title":"",

"category":"",

"importance\_score":9,

"impact":"",

"reason":"",

"trend":""

}

6\. Trend Analyzer 趋势分析 ✅



目标：



生成：



国内视角

海外视角

信息差

趋势判断

机会分析



输出类似：



国内：

关注产业落地、国产替代



海外：

关注风险、安全、资本



趋势：

Agent商业化

算力瓶颈

开源模型竞争

当前版本



可以认为：



AI-Tech-Radar v2.5



已经具备：



✅ 数据采集

✅ AI理解

✅ 信息筛选

✅ 趋势分析

✅ 日报生成



已经建立的设计理念



不要硬编码。



采用：



配置驱动



三个核心：



sources.yaml



负责：



“去哪里获取信息”



例如：



RSS

GitHub

arXiv

YouTube

X

Reddit

keywords.yaml



负责：



“关注什么”



例如：



LLM

Agent

RAG

MCP

Robotics

GPU

prompts/



负责：



“AI如何思考”



例如：



daily\_report.yaml



控制日报风格。



数据源规划



未来增加：



第一优先级



官方：



OpenAI

Google DeepMind

Anthropic

Meta AI

NVIDIA



研究：



arXiv

Hugging Face Papers



开发：



GitHub

第二优先级



社区：



Reddit

Hacker News



视频：



YouTube AI频道



社交：



X/Twitter AI账号白名单

想达到的日报效果



目标不是：



“新闻摘要”。



而是：



“科技情报分析”。



类似：



早上好，我先扫描全球科技信息。



今日重点：



AI大模型：



xxx



算力：



xxx



国内外区别：



中国：

关注商业落地



海外：

关注安全和资本风险





趋势判断：



未来3-6个月：



1\.

2\.

3\.





给开发者建议：



学习：

Agent

MCP

RAG

AI自动化

下一步开发路线

Task012：RAG知识库 ⭐（下一阶段）



目标：



让系统可以回答：



例如：



最近30天 AI Agent 有哪些变化？



DeepSeek 和 OpenAI 路线区别？



最近有哪些创业机会？



基于自己的数据库回答。



Task013：个人AI情报助手



增加：



每日推送

Telegram/邮件

自动通知

Task014：Web Dashboard



增加：



网页界面：



今日雷达



趋势图



搜索



AI问答

当前建议



现在不要疯狂加数据源。



先：



运行几天。



观察：



评分是否准确

日报质量

哪些信息源价值最高



然后再优化。



给下一次 Codex 的开发原则



保持：



Python 3.12

模块化

配置优先

不破坏已有 Collector

新功能独立模块

所有数据统一 Article 格式

增加日志

增加测试

下一次对话开场



可以直接说：



继续 AI-Tech-Radar 项目，目前已经完成 v2.5（RSS/GitHub采集、DeepSeek分析、Importance Scoring、Trend Analyzer），下一步准备做 Task012：RAG知识库。



以上就是完整上下文。下一次复制即可继续。

