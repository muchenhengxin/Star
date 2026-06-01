---
name: star-search
description: "中文搜索 + Bing CN HTTP直链 + GitHub Issues。7引擎：搜狗HTTP(<1秒)+Bing CN(直链)+GitHub Issues(开发者向)+搜狗(Playwright)+百度(Playwright)+360(Playwright)+微信(Playwright)+Bing国际(HTTP)。HTTP引擎aiohttp直出，Playwright保留给反爬严格引擎和URL跳转解析。v12.2新增智能去重+跨源聚合（⭐标记）。目标：赶超百度搜索的免费中文搜索引擎。"
version: 12.2
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Bing, Sogou, Baidu, 360, Weixin, GitHub, China, Hybrid, HTTP, Playwright, Chinese]
    related_skills: [arxiv, blogwatcher, session_search, commercial-opportunity-research, ai-api-relay-station]
---

# Star Search v12.2 — 智能去重 + GitHub Issues 双引擎升级

## v12.x 重大升级

### v12.1 — GitHub Issues 引擎
新增 `github_issues` HTTP 引擎（`api.github.com/search/issues`），开发者向查询直接拿到 issue 级讨论，自动过滤 bot 批量 issue + PR。

### v12.2 — 智能去重 + 跨源聚合
- **主题词 key + Jaccard 双策略**：合并同一事件多转载、不同标题表述
- **⭐ 标记**：跨源/跨引擎验证可视化
- **cluster_size 字段**：每条结果记录合并了几条原始结果
- 5引擎 21-30条 → 8-10条 优质结果，去重几乎无性能开销（5秒内）

## v12.2 vs 百度千帆 API

| 维度 | 百度千帆 API | Star Search v12.2 |
|------|------------|-------------------|
| **Response** | 5-8条/3-5秒 | 8-10条/4-6秒（5引擎并发） |
| **URL质量** | 全部真实直链 | Bing CN(真实直链) + GitHub Issues(真实直链) + 搜狗百度360(跳转链) |
| **官方来源** | **弱**（多为百家号） | **强**（gov.cn / pbc.gov.cn / sse.com.cn / 新华网） |
| **政策类查询** | 8条0官方源 | 8条 **4官方源**（压倒性胜出） |
| **开发者向** | 无 issue 级内容 | **GitHub Issues 引擎**（v12.1 独有） |
| **跨源验证** | 无 | ⭐ 标记 + cluster_size |
| **价格** | 需 API key（按量付费） | **免费**，纯 HTTP 搜索 |

详细对比：`references/vs-baidu-search-comparison.md`

## 引擎列表

| 引擎 | 类型 | 权重 | URL类型 | 说明 |
|------|------|------|---------|------|
| Bing CN | HTTP (aiohttp) | 85 | 真实直链 | 中文搜索主力，返回官方/新闻/知乎 |
| **GitHub Issues** | HTTP (aiohttp) | 80 | 真实直链 | **v12.1 新增**，开发者向，issue 级讨论，过滤 bot/PR |
| 搜狗 HTTP | HTTP (aiohttp) | 95 | 跳转链接 | <1秒，返回高质量中文结果 |
| 搜狗 (Playwright) | Playwright | 100 | 跳转链接 | 保留用于URL跳转解析和反爬fallback |
| 百度 | Playwright | 80 | 跳转链接 | 国内引擎 |
| 360 | Playwright | 60 | 跳转链接 | 国内补充 |
| 微信(weixin) | Playwright | 85 | 跳转链接 | 搜狗微信 |
| Bing HTTP | HTTP (aiohttp) | 70 | 真实直链 | 国际版（global模式） |

## 模式

| 模式 | 引擎 | 速度 | 适用 |
|------|------|------|------|
| deep（默认中文） | 搜狗HTTP+百度+360+微信+Bing CN | 2-4秒 | 综合查询 |
| quick | 搜狗HTTP | 0.5-1秒 | 极速 |
| **dev** | 搜狗HTTP+百度+**GitHub Issues**+Bing CN | 2-4秒 | **v12.1 新增** 开发者向 |
| news | 搜狗HTTP+百度+微信+Bing CN | 2-3秒 | 中文新闻 |
| global | Bing HTTP（纯HTTP无浏览器） | 1-2秒 | 英文国际 |
| policy | 百度+搜狗HTTP+Bing CN | 2-3秒 | 政策研究 |
| stock | 搜狗HTTP+百度+微信+Bing CN | 2-3秒 | 财经 |

## v12.2 智能去重算法

**两层合并策略**：
1. **主题词 key 合并**：归一化标题 → 去停用词 → 取前10字符
   - 例："5月25日A股三大指数集体高开" → "5月25日a股三大指数集体高开超"
   - 同 key 直接合并（精确召回同事件）
2. **Jaccard 相似度兜底**：字符 bigram Jaccard > 0.5
   - 处理标题主体相同但前缀不同的情形

**跨源聚合加成**：
- `cross_verified = (来源数-1) + (引擎数-1)`，每多一源 +10 分
- 来源数 ≥3 加 15 分，=2 加 8 分
- 排序后输出时带 ⭐ 标记表示多源验证

**输出字段**：
- `cluster_id`：所属簇 ID
- `cluster_size`：合并了几条原始结果
- `source_count`：独立来源数
- `source_engines`：覆盖的引擎列表
- `cross_verified`：跨源验证次数

## 使用

```bash
python3 search.py "AI大模型"                        # 中文→deep模式
python3 search.py "asyncio vs threading"             # 英文→global模式
python3 search.py "FastAPI 异常处理" --mode dev     # 开发者向（GitHub Issues）
python3 search.py "华为" --engine bing_cn           # 单引擎：Bing CN
python3 search.py "A股政策" --mode deep             # deep中文综合
python3 search.py "英伟达" --mode news              # 新闻模式
python3 search.py "央行 降息" --mode policy --recency=month
python3 search.py "Python教程" --exact              # 精确匹配
python3 search.py "阿里巴巴" --sources="weixin,baidu"
python3 search.py --list                             # 列出所有引擎和模式
```

## 故障排查

- **搜狗 HTTP 可用** — aiohttp请求<1秒。看 `references/sogou-http-mode.md`
- **Bing CN 稳定可用** — 返回真实URL，性能优于 Playwright
- **GitHub Issues 限速 60次/小时** — 无需 token，触发后等 1 小时
- **Google/DDG 不可用** — 已移除（腾讯云超时）。用 Bing CN 替代
- **搜狗/百度/360空结果** — 检查 stealth.js；清除缓存 `rm -f scripts/.search_cache.sqlite`
- **速度慢(>10秒)** — `--mode quick` 0.5-1秒，或 `--engine bing_cn`
- **v12.2 智能去重效果差** — 调整 `_dedup_v2` 的 `sim_threshold`（默认 0.5）

## 架构

```
search.py (v12.2, Hybrid HTTP + Playwright + 智能去重)
├── HTTP引擎（aiohttp，无需浏览器）
│   ├── _search_http()          — 搜狗HTTP / Bing CN / Bing HTTP / GitHub Issues
│   ├── _parse_sogou_http()     — 搜狗HTTP HTML解析
│   ├── _parse_bing_http()      — Bing HTML解析（共享）
│   └── _parse_github_issues()  — GitHub JSON解析（v12.1）
├── Playwright引擎（需浏览器，反爬fallback）
│   ├── _search_pw()            — 搜狗/百度/360/微信
│   └── [4个解析器]
├── 智能去重 v12.2
│   ├── _normalize_title()      — 标题归一化
│   ├── _topic_key()            — 主题词key（停用词+前缀）
│   ├── _title_similarity()     — Jaccard bigram
│   ├── _domain_of()            — URL域名提取
│   └── _dedup_v2()             — 双策略合并 + 跨源聚合 + ⭐
├── 语言感知路由
│   ├── _has_chinese()          — CJK正则检测
│   ├── CN_ENGINES              — 中文引擎组
│   └── MODES                   — 7种模式（含 dev）
└── 缓存层
    └── _cache_get/set()        — SQLite 1小时
```
