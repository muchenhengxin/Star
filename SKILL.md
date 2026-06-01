---
name: star-search
description: "中文搜索 + Bing CN HTTP直链 + GitHub Issues + 智能缓存。7引擎：搜狗HTTP(<1秒)+Bing CN(直链)+GitHub Issues(开发者向)+搜狗(Playwright)+百度(Playwright)+360(Playwright)+微信(Playwright)+Bing国际(HTTP)。v12.2 智能去重+⭐跨源标记，v13 分桶TTL缓存+query归一化。目标：赶超百度搜索的免费中文搜索引擎。"
version: 13.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Bing, Sogou, Baidu, 360, Weixin, GitHub, China, Hybrid, HTTP, Playwright, Chinese, Cache]
    related_skills: [arxiv, blogwatcher, session_search, commercial-opportunity-research, ai-api-relay-station]
---

# Star Search v13.0 — 智能缓存层 + v12.x 全部特性

## v12.x/v13.x 重大升级

### v13.0 — 智能缓存层
- **query 归一化 key**：去标点/空格/大小写，让"Python 教程"和"python 教程!!!"复用同一缓存
- **分桶 TTL**：news/policy/stock 5-10分钟（保时效），dev/global 1小时（保效率）
- **桶复用**：缓存永远存 max(请求num, 20) 条，num=5/8/10 同一桶
- **命中率统计**：stderr 输出 `[cache] 命中率 X/Y = Z% · 写入 N 次`

### v12.2 — 智能去重 + 跨源聚合
- **主题词 key + Jaccard 双策略**：合并同一事件多转载、不同标题表述
- **⭐ 标记**：跨源/跨引擎验证可视化
- **cluster_size 字段**：每条结果记录合并了几条原始结果
- 5引擎 21-30条 → 8-10条 优质结果，去重几乎无性能开销（5秒内）

### v12.1 — GitHub Issues 引擎
新增 `github_issues` HTTP 引擎（`api.github.com/search/issues`），开发者向查询直接拿到 issue 级讨论，自动过滤 bot 批量 issue + PR。

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

开发记录（v12+ 引擎复用 + 去重决策）：
- `references/v12-engine-addition-recipe.md` — 新 JSON API 引擎三步接入模板（GitHub Issues 类）
- `references/dedup-merge-decision-log.md` — v12.2 智能去重算法的迭代决策与产品判断

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

## v13.0 智能缓存算法

**分桶 TTL 配置**：

| 模式 | TTL | 理由 |
|------|-----|------|
| news | 5分钟 | 时效强敏感 |
| policy | 10分钟 | 政策解读时效中等 |
| stock | 5分钟 | 行情时效强敏感 |
| quick | 30分钟 | 用户高频同查 |
| deep | 30分钟 | 综合查询，中等 |
| dev | 1小时 | 技术内容稳定 |
| global | 1小时 | 国际版稳定 |

**Query 归一化策略**：
- 小写 + 去前后空格
- 标点/特殊符号替换为空格
- 多个空格合并为单空格
- 例：`"Python  asyncio  教程!!!"` → `"python asyncio 教程"` 复用同一桶

**桶复用机制**：
- 缓存写入时存 `max(请求num, 20)` 条
- 缓存读取时按 `请求num` 切前 N 条
- num=5/8/10/15 都从同一 20+ 桶里取
- 命中率实测：重复查询 + 近似查询共节省 4-6 秒

**命中率统计**（stderr）：
```
[cache] 命中8条 (key=45576962.. TTL=3600s 剩0s前)
[cache] 命中率 0/1 = 0% · 写入 0 次
```

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
search.py (v13.0, Hybrid HTTP + Playwright + 智能去重 + 智能缓存)
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
├── 智能缓存 v13.0
│   ├── _normalize_query()      — query归一化（去标点/空格）
│   ├── MODE_TTL                — 分桶TTL配置
│   ├── _cache_key()            — 不含num（桶复用）
│   ├── _cache_get/set()        — 分桶TTL + 桶复用
│   └── _cache_stats_report()   — 命中率统计
├── 语言感知路由
│   ├── _has_chinese()          — CJK正则检测
│   ├── CN_ENGINES              — 中文引擎组
│   └── MODES                   — 7种模式（含 dev）
└── URL解析（Playwright跳转链）
    └── _resolve_results()      — 并发解析redirect URLs
```
