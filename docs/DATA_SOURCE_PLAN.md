\# AI Tech Radar 数据源规划



\## 目标



构建一个高质量 AI 科技情报系统。



目标不是收集大量信息，而是发现：



\- 最新 AI 技术突破

\- 开源项目趋势

\- 研究方向变化

\- 社区热点

\- 商业机会



核心原则：



> 高质量信息 > 信息数量



\---



\# 数据源分层



\## Layer 1：官方信息源（最高可信度）



用途：



获取第一手官方动态。



类型：



\- 模型发布

\- API更新

\- 产品变化

\- 技术博客





推荐来源：



\## OpenAI



关注：



\- 新模型

\- API

\- Agent

\- 产品更新





\## Google DeepMind



关注：



\- AI研究

\- Gemini

\- 多模态

\- Robotics





\## Anthropic



关注：



\- Claude

\- AI安全

\- Agent





\## Meta AI



关注：



\- Llama

\- 开源模型





\## NVIDIA Developer



关注：



\- GPU

\- CUDA

\- AI基础设施





实现：



RSS Collector



数据类型：



official





\---



\# Layer 2：论文与研究数据源



用途：



发现未来技术方向。



特点：



论文通常领先新闻。





\## arXiv



关注分类：



\- cs.AI

\- cs.CL

\- cs.LG

\- cs.RO





关键词：



\- LLM

\- Agent

\- Transformer

\- Reasoning

\- Multimodal

\- Robotics





数据：



paper





\---



\## Hugging Face Papers



关注：



\- 最新论文

\- 开源模型

\- Demo





数据：



paper





\---



\# Layer 3：开发者生态



用途：



发现正在快速增长的技术。





\## GitHub



关注：



\- Trending

\- Star增长

\- Release

\- Issue活跃度





重点方向：



\- LLM

\- Agent

\- RAG

\- MCP

\- AI Framework





数据：



github





\---



\## Hacker News



关注：



\- AI创业

\- 工程实践

\- 技术讨论





数据：



community





\---



\# Layer 4：社区数据



用途：



发现真实用户反馈。





\## Reddit



推荐社区：



\- r/MachineLearning

\- r/LocalLLaMA

\- r/artificial





过滤：



必须经过AI评分。



避免：



\- 低质量讨论

\- 重复新闻





数据：



community





\---



\# Layer 5：视频与社交媒体



\## YouTube



目标：



不是抓视频。



获取：



\- 标题

\- 描述

\- 发布时间





重点：



\- AI研究者

\- 开源作者

\- ML工程师





数据：



video





\---



\## X / Twitter



用途：



最快速信息源。





策略：



不要全量抓取。





采用：



账号白名单。





关注：



\- AI研究员

\- 开源作者

\- 公司技术负责人





数据：



social





\---



\# 数据源优先级



\## 第一阶段（必须）



优先实现：



1\. 官方RSS

2\. GitHub

3\. arXiv

4\. Hugging Face





原因：



质量高，稳定。





\---



\## 第二阶段



增加：



1\. Reddit

2\. YouTube

3\. X





原因：



信息速度快，但是噪音高。





\---



\# 数据统一格式



所有来源必须转换成：



Article





结构：



```json

{

&#x20;   "title": "",

&#x20;   "content": "",

&#x20;   "url": "",

&#x20;   "source": "",

&#x20;   "source\_type": "",

&#x20;   "published\_time": ""

}

