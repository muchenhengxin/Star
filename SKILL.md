---
name: star-search
description: "Use when asked to search the web, find online information, research topics, get news, look up Chinese content, or check A股/finance/tech news. **v20.33 — 意图理解 94.4%/59.3% + KB 180 实体 + Cloudflare Bot 保护应对**! star-search 是标准 Model Context Protocol server (4 tools) 给 Claude Desktop/Cursor/Hermes 等 LLM agent 调用. 公网 HTTP/SSE: https://search.token-star.cn/mcp/sse . v20 实战 35-87: 速度 6s→0.2s + SSE 流式 + 多轮 + 4 格式 + 监控 + i18n + 语义搜索 + **AI 智能层实战 62-86** (super_brain + multi_search + entity_card + cross_verify + intent_strategy) + **Cloudflare Bot 保护实战 87** (Bot Fight Mode 阻塞 skill/API, 必须 WAF 白名单). 16 引擎 + 智能意图识别 (4 batch 108 query 测试) + 5 实战核心方法论."
version: 20.34.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Bing, Sogou, Baidu, 360, Weixin, Toutiao, Zhihu, GitHub, China, Hybrid, HTTP, Playwright, Chinese, Cache, API, OpenAI, Cron, Incremental, CSDN, Cnblogs, Eastmoney, CLS, Sina, Sohu, Quality, Explain, Debug, RSS, Ithome, 36kr, Sspai, Oschina, Woshipm, Global, Public, HTTPS, Frontend, SmartRouting, Finance, MCP, JSON-RPC, SSE, LLM-Answer, Perplexity-Mode, Honest-LLM, Honest-Search, v20, Speed-Optimization, Streaming, Multi-Turn, Monitoring, Prometheus, Grafana, Structured-Output, Favorites, Academic-Search, Code-Search, Intent-Understanding, Cloudflare-Bot-Protection, KB-Card]
    related_skills: [arxiv, blogwatcher, session_search, commercial-opportunity-research, ai-api-relay-station, building-mcp-servers, native-mcp]
    references:
      - v16-v17-legacy-archive.md
      - v16-finance-mode-and-smart-routing.md
      - v16-public-deployment-and-daemon.md
      - v17-frontend-answer-card.md
      - v17-llm-answer-quality-strategy.md
      - mcp-server-zero-deps.md
      - site-bing-proxy-pattern.md
      - incremental-cache-pattern.md
      - llm-answer-honest-prompt.md
      - ai-native-search-transformation.md
      - intent-understanding-test-bench.md
      - intent-detection-rule-priority.md
      - cloudflare-bot-protection.md
---

# Star Search v20.33 — 速度/流式/多轮/稳定/学术/结构化/收藏/监控/AI 智能层/Cloudflare 应对 一体化中文搜索

> 本 skill 已从 v8.3 演进到 v20.33。v16-v17 归档在 references/v16-v17-legacy-archive.md。GitHub: https://github.com/muchenhengxin/Star . 公网: https://search.token-star.cn (HSTS+LE证书+nginx 反代)。

## ⚠️ 关键必读 (v20.33 新增)

### Cloudflare Bot 保护 (实战 87)

**症状**: skill/MCP/API 直接调 search.token-star.cn → 403/503 弹人机验证
**根因**: Cloudflare 把 Python/curl User-Agent 当 bot (无 JS 验证 + 无 Cookie + 来源 IP 是腾讯云)
**关键认识**: **Web 浏览器访问不受影响**, 只有 skill/API/CLI 受影响

**3 选 1 修复方案**:
1. **A. 关闭 Bot Fight Mode** (推荐, 5min) — dash.cloudflare.com → token-star.cn → Security → Bots → Bot Fight Mode Off
2. **B. WAF Custom Rule 白名单** (推荐, 永久) — 加规则: `ip.src eq <server_ip>` 或 `http.user_agent contains "Star-Search-Skill"` → Skip: Super Bot Fight Mode
3. **C. 改 User-Agent + Headers** (2min, 不彻底) — `User-Agent: Mozilla/5.0 ...` + `Accept-Language: zh-CN`

**API Token 权限要求** (用 A/B 时): 必须有 `Zone WAF Edit` + `Zone Settings Edit` + `Zone Bot Management Edit`。**Token 默认 `API Tokens Write` 权限不够** (实战 87 验证)。

**Token 验证**: `curl https://api.cloudflare.com/client/v4/user/tokens/verify -H "Authorization: Bearer <TOKEN>"` → `{"success":true, "status":"active"}`
**Zone ID 获取**: https://dash.cloudflare.com/?to=/:account/:zone → 选 token-star.cn → 右下角 API 框
**关 Bot Fight Mode**: `PATCH /zones/{zone_id}/settings/bot_fight_mode` body `{"value":"off"}`

完整复盘见 `references/cloudflare-bot-protection.md`

## 版本历史 (v20.32-20.33)

| 版本 | 日期 | 主要变更 |
|---|---|---|
| **v20.33.0** | 2026-06-17 | **实战 78+79-81+85+86 意图理解 + 实战 87 Cloudflare 应对**（detect_entity_type 17 规则 / KB 180 实体 / 学术类 query→academic 规则 / 4 批 108 query 回归 BRAIN 87.9%→94.4% STRAT 48.6%→59.3% / **Cloudflare Bot Fight Mode 阻塞 skill/API** — 必须 CF 后台加 WAF Custom Rule 白名单 UA/IP 或关 Bot Fight Mode） |
| v20.32.0 | 2026-06-17 | 实战 85: KB 160+ 实体 (BRAIN 94.4%/STRAT 56.5%) |

[完整 v20.6 - v20.27 历史及 v16-v17 章节见 references/v16-v17-legacy-archive.md]

## 实战 78+85+86 意图理解大幅优化 (v20.33)

### 4 批 108 query 全面回归 (并发 8 线程, 90s 跑完)

| 阶段 | BRAIN (intent) | STRAT (entity_type) | 两者都准 |
|---|---|---|---|
| 实战 73 之前 | ~70% | ~30% | ~25% |
| 实战 78 之后 | 91.7% | 53.7% | 51.9% |
| 实战 85 (KB 180+) | **94.4%** | 56.5% | 55.6% |
| 实战 86 (学术规则) | 92.6% | **59.3%** | **58.3%** |

### detect_entity_type 17 规则优先级 (实战 78 调试 8 轮才到 10/10)

**口诀**: **自述 → 模式 → intent → fallback**, 段内 academic_set 优先 company_hint

**17 规则清单**:
1. 1-2 字中文 → general (保留 KB 优先路径, 不立刻截胡)
2. 自述句 (我/咱们) → general
3. 模式硬编码: "X 官网" → company / "X 是什么" → academic+company+product / "X 简介" → company+product
4. 实战 86: 学术/教程/方法 query → academic ("教程/入门/怎么/如何/备考/申请/步骤")
5. intent=news → news
6. intent=transaction → shopping
7. intent=navigation → company/product (4-8 字中文)
8. intent=info: 人物 (简历/生平/先生/女士) → person / KB hint → 对应类 / category 决定 fallback
9. intent=comparison: 第一 entity 类型 (公司/产品/学术)
10. KB hint (大/小写不敏感) → 对应类
11. 中文 2-8 字 + category 在 (tech/shopping/social) → product
12. 中文 2-4 字 + 后缀 (招聘/招聘) → general
13. 英文 entity → company
14. 拼音 query → 中文重写
15. 错别字 → 常见词纠正
16. 2-4 字中文 entity 走 KB 优先
17. 极长 query 拆 entity

**关键调试 8 轮发现** (从 26/40 → 40/40):
- 规则顺序决定一切 (intent 优先 vs KB 优先 冲突)
- KB_HINT 大小写不敏感 (openai vs OpenAI)
- "X 是什么" 模式 必须在 intent 之前 (否则 info 模式截胡)
- "X 官网" 必须 strip 官网后看 entity ("华为官网" → company, 拆出"华为")
- 中文 2-4 字 entity 不能直接判 person (误判"微信"为"韦信先生")

### KB 180+ 实体 (实战 85)

- **BUILTIN_KB_EXTRA** (13): 马斯克/埃隆·马斯克/LLM/5G/GPT/GPT-4/GPT-4o/o1/Claude/Transformer/RAG/AI
- **BUILTIN_KB_EXTRA2** (90): 15 人物 (乔布斯/盖茨/雷军/任正非/马云/马化腾/李彦宏/刘强东/张一鸣/黄仁勋/巴菲特/芒格/陆奇/李开复/奥特曼) + 15 公司 (Spotify/Netflix/Uber/Airbnb/Salesforce/Oracle/SAP/Cisco/IBM/VMware/联想/中兴/大疆/滴滴/快手/完美世界/米哈游/保时捷/宝马/奔驰/奥迪/茅台/五粮液/星巴克/可口可乐/百事可乐/迪士尼) + 12 AI 产品 (Sora/Gemini/Llama/Mistral/Anthropic/Perplexity/Notion/Figma/Slack/钉钉/飞书/Zoom) + 11 概念 (区块链/比特币/以太坊/NFT/Web3/元宇宙/云计算/大数据/物联网/量子计算/深度学习) + 11 游戏 (黑神话/原神/王者荣耀/LOL/我的世界/宝可梦/塞尔达/漫威/DC/哈利波特/三体) + 10 食物饮料 (咖啡/茶/茅台/五粮液/可口可乐/百事/星巴克/喜茶/蜜雪冰城) + 5 地点 (故宫/长城/迪士尼/上海迪士尼/环球影城)
- **BUILTIN_KB** (50+ 原始): 韭研公社/雪球/同花顺/华为/比亚迪/苹果/微软/谷歌/OpenAI/Claude/微信/微博/知乎/B站/抖音/Python/Rust/GitHub
- **BUILTIN_KB_HINT** 动态合并: `_build_kb_hint()` 合并 3 个 KB (180+ 实体)

### 真网址强优先 (实战 81)

- **answer.py 强约束 inject KB official_url 到 prompt**
- `generate_answer(query, results, mode, history, fmt, brain_ctx, entity_card_url=None)`
- prompt 段: "你的答案中**必须包含这个网址**"
- **公网 5 query 100% 引用 KB 网址** (jiuyangongshe.com/weixin.qq.com/openai.com/gpt-4)

## 4 批 108 query 测试方法论 (实战 77 + 78 + 85 + 86)

**测试模板** (scripts/test_intent_108.py):
- BATCH1 (37): 导航/工商/购物/对比/教程/资讯/人物/产品/视频/边界
- BATCH2 (30): 模糊/多 entity/极短/中英/复合/命令
- BATCH3 (20): 金融/医疗/教育/法律/汽车/房产 垂直
- BATCH4 (20): 错拼/极简/讽刺/方言/极长/乱码

**跑法**:
```python
from concurrent.futures import ThreadPoolExecutor
import super_brain, intent_strategy
def test(q): bi = super_brain.analyze_query(q[0], use_cache=False); s = intent_strategy.strategy_for_query(q[0], bi); ...
with ThreadPoolExecutor(max_workers=8) as ex: results = list(ex.map(test, ALL))
```

**关键**: `rm -f brain_cache.json` 清缓存 (避免假阳性)
**评分**: brain_ok = (intent==exp), strat_ok = (entity_type==exp), both_ok = brain_ok and strat_ok

完整模板见 `scripts/test_intent_108.py`

## 实战 87 Cloudflare Bot 保护 (v20.33 新章节)

[完整章节在 references/cloudflare-bot-protection.md]

**用户原话** (2026-06-17): "Star Search 被 Cloudflare 保护了（人机验证）, API 无法直接调用. 这个 skill 无法使用了, 是怎么回事, 人机验证不是用在 web 端吗, skill 应该可以正常使用啊"

**核心原则 (用户硬强调)**: "方案A, 这个 skill, 是免费使用的, 这个是咱们的核心原则"
→ 必须**永久方案** (WAF 白名单 / 关 Bot Fight Mode), 不能用应急方案 (改 UA 一次性)

**根因分析**:
- Cloudflare 看到: 来源 IP (腾讯云) + User-Agent (Python/curl) + 无 Cookie + 无 JS
- 判定 bot → 弹人机验证
- **影响**: Web 浏览器 ✓ / skill/MCP/API ✗

**3 步解决**:
1. 拿 CF_API_TOKEN (要 `Zone WAF Edit` + `Zone Settings Edit` + `Zone Bot Management Edit`)
2. 拿 CF_ZONE_ID (token-star.cn 域名)
3. PATCH 关 Bot Fight Mode + 加 WAF Custom Rule

**API 端点**:
- `GET /client/v4/user/tokens/verify` — 验证 token
- `GET /client/v4/zones` — 列 zones (要 zones:read)
- `PATCH /zones/{zone_id}/settings/bot_fight_mode` body `{"value":"off"}` — 关 Bot Fight Mode
- `PUT /zones/{zone_id}/rulesets/{ruleset_id}/rules` — 加 WAF Custom Rule

完整 API + 复盘见 `references/cloudflare-bot-protection.md`

## 实战 86 学术类 query 强规则 (v20.33)

**触发条件** (任一): "教程/入门/学习/教学/指南/方法/技巧/备考/申请/步骤/复习/练题/做法/怎么用/怎么学/怎么选/怎么治/怎么写/怎么做/怎么配/怎么调/如何用/如何学/如何选/如何治/如何写/如何做/如何配/如何调"

→ 直接判 `academic`

**STRAT 提升**: 56.5% → 59.3% (+2.8%)
**两者都准**: 55.6% → 58.3% (+2.7%)

**位置**: detect_entity_type 模式硬编码之后, intent 优先之前
