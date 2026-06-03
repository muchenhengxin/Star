---
name: star-search
description: "中文搜索 + 16 引擎直搜 + 智能缓存 + OpenAI-compatible API + 定时增量 + 质量标识。16引擎：搜狗HTTP(<1秒)+Bing CN(直链)+GitHub Issues(开发者向)+头条+知乎+微信+CSDN+博客园+东方财富+财联社+腾讯云开发者+新浪财经+搜狐(site:bing代理，免反爬)+搜狗(Playwright)+百度(Playwright)+360(Playwright)+微信(Playwright)+Bing国际(HTTP)。v12.2 智能去重+⭐跨源标记，v13 分桶TTL缓存+query归一化，v14 OpenAI API 暴露+增量追加，v15 site:bing 直搜+定时 cron 客户端，v15.1 新增 7 个 site 代理引擎，v16 修复 sogou KeyError + 质量标识🌟🌟🌟 + --explain 评分透明，v16.1 加 5 个 RSS 引擎 (ithome/36kr/sspai/oschina/woshipm) + global mode 中英双源路由 + cron_refresh 5 个 preset 模板，v16.2 公网部署 (search.token-star.cn HTTPS) + 11 HTTP 引擎独立工作 (Playwright 优雅降级)。目标：赶超百度搜索的免费中文搜索引擎 + 给 LLM agent 当实时事实层。"
version: 16.2
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Bing, Sogou, Baidu, 360, Weixin, Toutiao, Zhihu, GitHub, China, Hybrid, HTTP, Playwright, Chinese, Cache, API, OpenAI, Cron, Incremental, CSDN, Cnblogs, Eastmoney, CLS, Sina, Sohu, Quality, Explain, Debug, RSS, Ithome, 36kr, Sspai, Oschina, Woshipm, Global, Public, HTTPS, LLM-Tool, MCP-Ready]
    related_skills: [arxiv, blogwatcher, session_search, commercial-opportunity-research, ai-api-relay-station]
---

# Star Search v16.2 — 公网 HTTPS 部署 + 11 HTTP 引擎独立工作

## v16.2 — 公网部署 + 优雅降级（2026-06-03）

### 公网部署

**子域**：`https://search.token-star.cn`

- **架构**：独立子域（不影响主域 token-star.cn 的 New API / Agent Platform）
- **DNS**：犀牛加 A 记录 `search → 62.234.39.247`
- **证书**：Let's Encrypt 独立签发，自动续期
- **API server**：FastAPI 跑在 `62.234.39.247:5000` (ubuntu 用户 systemd)

**5 个端点全部上线**：
```
https://search.token-star.cn/v1/health        → 200, 70ms
https://search.token-star.cn/v1/search        → 200, ~300ms (tech_news 模式)
https://search.token-star.cn/v1/search/refresh → 增量追加
https://search.token-star.cn/v1/modes         → 11 modes
https://search.token-star.cn/v1/engines       → 16 engines
```

### 引擎实际可用矩阵

| 引擎类型 | 数量 | 公网状态 | 备注 |
|---------|------|---------|------|
| HTTP 引擎 | **11** | ✅ 全工作 | 搜狗HTTP/Bing CN/Bing HTTP/GitHub Issues/csdn/cnblogs/eastmoney/cls/tencent_cloud/sina_finance/sohu + 头条/知乎/微信 (site:bing) |
| RSS 引擎 | **5** | ✅ 全工作 | rss_ithome/rss_36kr/rss_sspai/rss_oschina/rss_woshipm |
| Playwright 引擎 | 4 | ⚠️ 需 sudo | sogou/baidu/360/weixin 浏览器抓取，CDN 下载被阻断 |

### Playwright 优雅降级（v16.2 新增）

**之前**：playwright 装不上 → 11 HTTP 引擎都报 `ImportError: playwright async_api`
**现在**：try/except 导入 + `_PLAYWRIGHT_OK` 标志 + `_ensure_browser` 守卫

```python
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False

async def _ensure_browser(pw):
    if not _PLAYWRIGHT_OK:
        raise RuntimeError("playwright not available, use HTTP engines")
    ...
```

**效果**：11 HTTP 引擎在 5000 端口独立工作，sogou/baidu/360/weixin 自动跳过（不抛异常），用户用 `--engine sogou` 才会触发 PW 缺失错误

### 部署脚本

`scripts/deploy.sh` (1324 chars) — 完整部署流程（apt 装包 + 装 playwright + 启 systemd）
`scripts/setup-root.sh` (2082 chars) — root context 启动 + apt 装 libatk (Playwright 系统依赖)
`scripts/nginx-api.token-star.cn.conf` (1618 chars) — 实际未用（走恒星01 的 search.token-star.cn 子域方案）

### 实战耗时（公网 RTT）

```
tech_news "华为鸿蒙"     → 3 results, 436ms
global  "GPT-4 vs Claude" → 3 results, 361ms
health                   → 70ms
```

### 不动 / 未做的部分

- ❌ 浏览器引擎完整启用（需 root sudo 装 chromium-headless-shell-1223 系统依赖）
- ❌ 国际引擎（ddg/brave/scholar — 本机 GFW 限制，需 token-star.cn 备案 + 独立 IP）
- ❌ MCP server 化（v17.0 计划）
- ❌ Web UI（v18.0 计划）

---

## v16.0 — 鲁棒性 + 可解释性（2026-06-02）

### 修复：sogou 引擎 KeyError 反复刷 stderr
- **根因**：`sogou` 误同时在 `HTTP_BASE_URLS` 和 `PW_BASE_URLS` 注册，但只在 `PW_PARSERS` 注册解析器
- **表现**：跑 deep mode 时搜狗会先走 HTTP → `HTTP_PARSERS['sogou']` KeyError → stderr 一直刷 → 用户视角"搜狗挂了"
- **修复**：`HTTP_BASE_URLS` 移除 sogou（保留 PW 注册），KeyError 消失
- **验证**：6/6 mode smoke test，0 错误，平均 3 秒

### 新增：质量标识 🌟🌟🌟
- **逻辑**：v12.2 已有 `cross_verified` 字段（跨源/跨引擎聚合数），但前端只显示 ⭐ 一个
- **新规则**：
  - `cross_verified >= 3` → 🌟🌟🌟（3+ 源验证，高可信）
  - `cross_verified >= 2` → 🌟🌟
  - `cross_verified >= 1` → 🌟
  - `= 0` → 无
- **示例**：华为鸿蒙 PC 排名第 1 标 🌟🌟🌟 (3 跨源)，第 2 标 🌟🌟

### 新增：--explain 调试模式
- **用法**：`python3 scripts/search.py "query" --explain`
- **输出**：每条结果下方打印 `📊 date_score · cross_verified=+40 · domain_auth=+8 · total=155`
- **目的**：让用户/调试者看到评分构成（不只看到一个 final score）
- **API 端**：`/v1/search` 返回的 results 已带 score/cross_verified 字段，调用方可自行渲染

## v12.x/v13.x/v14.x/v15.x 重大升级

### v15.1 — 7 个新 site:bing 直搜代理
- **csdn**: site:csdn.net — CSDN 技术博客（开发者向）
- **cnblogs**: site:cnblogs.com — 博客园（开发者向）
- **eastmoney**: site:eastmoney.com — 东方财富（财经）
- **cls**: site:cls.cn — 财联社（财经快讯）
- **tencent_cloud**: site:cloud.tencent.com — 腾讯云开发者（技术）
- **sina_finance**: site:finance.sina.com.cn — 新浪财经（财经）
- **sohu**: site:sohu.com — 搜狐（综合）
- **共 10 个 site: 代理引擎**（v15.1 + v15 头条/知乎/微信）
- **解析后过滤非目标域** + engine 标签真实
- **探测方法**：用 v15 _parse_bing_cn 实测 27 个域，7 个返回真实目标域结果

### v15.0 — 10 引擎直搜 + 定时增量
- **新增 3 个 site:bing 直搜代理**：`toutiao` (site:toutiao.com) / `zhihu` (site:zhihu.com) / `weixin` (site:mp.weixin.qq.com)
- **免反爬**：3 引擎纯 HTTP 走 cn.bing.com，0 浏览器，<1秒
- **域过滤**：解析后过滤非目标域名（toutiao=100%头条，zhihu=100%知乎，weixin=100%微信）
- **engine 标签真实**：解析器内部标 engine='toutiao/zhihu/weixin_bing'，区分 weixin_pw
- **cron 客户端** `scripts/cron_refresh.py`：异步并发拉多 query，JSONL 输出
- **Cron job 模板**：30 分钟跑 3 次，自动调 /v1/search/refresh

### ⚠️ Cron 调度两大坑（2026-06-02 实战）

用 `hermes cron create --script <path> --no-agent` 时：

1. **脚本必须放 `~/.hermes/scripts/` 下** — 绝对路径/家目录相对路径都会被拒
   ```
   ✗ /Users/lizhe/.hermes/scripts/foo.sh
   ✓ foo.sh  (相对 ~/.hermes/scripts/)
   ```

2. **Gateway 必须先启动**，cron 才会真正自动触发
   ```
   ✗ Gateway is not running — jobs won't fire automatically.
   ✓ hermes gateway start       # macOS launchd
   ✓ sudo hermes gateway install --system   # Linux 服务器
   ```

**新装 Hermes 必先 `hermes gateway install` + `start`，否则 cron job 永不跑。**

### v14.0 — OpenAI-compatible API 暴露 + 增量追加
- **FastAPI server** `scripts/api_server.py` 启动 `python3 scripts/api_server.py --port 9800`
- **5 个接口**：
  - `POST /v1/search` 主搜索（OpenAI-style body: query/mode/top/recency/exact/engine/sources）
  - `POST /v1/search/refresh` 增量追加（force_refresh 绕过缓存 + 与历史合并）
  - `GET /v1/health` 健康检查
  - `GET /v1/modes` 列出 7 模式
  - `GET /v1/engines` 列出 7 引擎
- **force_refresh 参数**：绕过缓存强制刷新，新结果标 `refresh=true`，历史标 `refresh=false`
- **Playwright 容错**：new_page 失败时跳过该引擎（不抛异常）
- **节省时间**：重复查询/刷新场景下从 5.5秒 → 1.2秒（节省 78%）

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
- `references/v16-engine-addition-checklist.md` — **v16 必看**：新引擎接入 4 dict 对齐 + 一行命令验证（搜狗 KeyError 教训）
- `references/dedup-merge-decision-log.md` — v12.2 智能去重算法的迭代决策与产品判断
- `references/v14-api-and-incremental-merge.md` — v14 FastAPI wrapper + force_refresh 增量追加 + Playwright 长进程容错（CLI→API 暴露的通用 pattern）
- `references/v15-site-bing-probe-results.md` — v15.1 27 域 site:bing 实测数据（哪些能拿到真实结果、哪些 Bing 索引不到）

## 引擎列表

| 引擎 | 类型 | 权重 | URL类型 | 说明 |
|------|------|------|---------|------|
| **Bing CN** | HTTP (aiohttp) | 85 | 真实直链 | 中文搜索主力，新华网/知乎/东方财富 |
| **GitHub Issues** | HTTP (aiohttp) | 80 | 真实直链 | **v12.1 新增**，issue 级讨论，过滤 bot/PR |
| **toutiao** | HTTP (site:bing) | 75 | 真实直链 | **v15 头条**，100% toutiao.com 文章 |
| **zhihu** | HTTP (site:bing) | 75 | 真实直链 | **v15 知乎**，100% zhihu.com 专栏/问答 |
| **weixin (bing)** | HTTP (site:bing) | 85 | 跳转链接 | **v15 微信公众号**，100% 微信文章 |
| **搜狗 HTTP** | HTTP (aiohttp) | 95 | 跳转链接 | <1秒，高质量中文结果 |
| 搜狗 (Playwright) | Playwright | 100 | 跳转链接 | URL 解析 + 反爬 fallback |
| 百度 | Playwright | 80 | 跳转链接 | 国内引擎 |
| 360 | Playwright | 60 | 跳转链接 | 国内补充 |
| 微信 (weixin_pw) | Playwright | 85 | 跳转链接 | 搜狗微信 |
| Bing HTTP | HTTP (aiohttp) | 70 | 真实直链 | 国际版 (global 模式) |

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

### CLI 模式

```bash
python3 search.py "AI大模型"                        # 中文→deep模式
python3 search.py "asyncio vs threading"             # 英文→global模式
python3 search.py "FastAPI 异常处理" --mode dev     # 开发者向（GitHub Issues）
python3 search.py "华为" --engine bing_cn           # 单引擎：Bing CN
python3 search.py "华为鸿蒙" --engine toutiao       # v15: 头条
python3 search.py "Python asyncio" --engine zhihu   # v15: 知乎
python3 search.py "DeepSeek V4" --engine weixin     # v15: 微信公众号
python3 search.py "asyncio 教程" --engine csdn      # v15.1: CSDN
python3 search.py "asyncio 教程" --engine cnblogs   # v15.1: 博客园
python3 search.py "A股 政策" --engine eastmoney     # v15.1: 东方财富
python3 search.py "央行 货币政策" --engine cls      # v15.1: 财联社
python3 search.py "asyncio 教程" --engine tencent_cloud  # v15.1: 腾讯云
python3 search.py "A股 政策" --engine sina_finance  # v15.1: 新浪财经
python3 search.py "鸿蒙 PC" --engine sohu           # v15.1: 搜狐
python3 search.py "A股政策" --mode deep             # deep中文综合
python3 search.py "英伟达" --mode news              # 新闻模式
python3 search.py "央行 降息" --mode policy --recency=month
python3 search.py "Python教程" --exact              # 精确匹配
python3 search.py "阿里巴巴" --sources="weixin,baidu"
python3 search.py --list                             # 列出所有引擎和模式
```

### API 模式（v14，推荐给 subagent/脚本）

```bash
# 启动 server
python3 scripts/api_server.py --port 9800

# 主搜索（5.5秒，4-5引擎并发）
curl -X POST http://127.0.0.1:9800/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"FastAPI 异常处理","mode":"dev","top":5}'

# 增量追加（1.2秒，强制刷新+合并历史）
curl -X POST http://127.0.0.1:9800/v1/search/refresh \
  -H "Content-Type: application/json" \
  -d '{"query":"FastAPI 异常处理","mode":"dev","top":8}'

# Python 客户端
import httpx
r = httpx.post('http://127.0.0.1:9800/v1/search', json={
    'query': '华为鸿蒙', 'mode': 'dev', 'top': 5
}).json()
for item in r['results']:
    print(f"{item['score']:5.1f}  {item['title']}")
```

### 定时增量模式（v15，subagent 监控）

```bash
# 单 query 拉一次（JSONL 输出到 stdout）
python3 scripts/cron_refresh.py --query "华为鸿蒙 PC" --mode dev

# 多 query 并发
python3 scripts/cron_refresh.py --queries "华为鸿蒙" "DeepSeek V4" --top 5

# 循环（每 1800 秒=30分钟 拉一次）
python3 scripts/cron_refresh.py --queries "..." --loop 1800

# 配合 cron job 调度（推荐给 subagent）
hermes cronjob create --schedule "every 30m" --prompt "..." \
  --skills star-search --name "我的监控"
```

## 故障排查

- **搜狗 HTTP 可用** — aiohttp请求<1秒。看 `references/sogou-http-mode.md`
- **Bing CN 稳定可用** — 返回真实URL，性能优于 Playwright
- **GitHub Issues 限速 60次/小时** — 无需 token，触发后等 1 小时
- **Google/DDG 不可用** — 已移除（腾讯云超时）。用 Bing CN 替代
- **搜狗/百度/360空结果** — 检查 stealth.js；清除缓存 `rm -f scripts/.search_cache.sqlite`
- **速度慢(>10秒)** — `--mode quick` 0.5-1秒，或 `--engine bing_cn`
- **v12.2 智能去重效果差** — 调整 `_dedup_v2` 的 `sim_threshold`（默认 0.5）
- **site:bing 引擎 0 命中** — 正常！Bing 对中文站索引不全。先用 `references/v15-site-bing-probe-results.md` 查表看该站是否标记为"无效"
- **本地 skill 目录被误删/丢失** — 从 GitHub 重建：`git clone https://github.com/muchenhengxin/Star.git ~/.hermes/skills/research/star-search`；再用 `git fetch --depth 10 && git reset --hard origin/main` 拉到最新 commit
- **git push 报 "Device not configured"** — 多半是 `gh` CLI 没了（hermes 默认 credential.helper 指向它）。先 `git config --global --remove-section credential` 干掉坏的 helper，再用环境变量 `GH_TOKEN=...` 或 `git -c "url.https://<PAT>@github.com/.insteadOf=https://github.com" push` 注入 PAT。注意：fine-grained PAT 默认只 metadata:read，需在 GitHub 端为该 token 勾选 Repository permissions → Contents: Read and write 才能 push

## 架构

```
search.py (v14.0, Hybrid HTTP + Playwright + 智能去重 + 智能缓存 + API)
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
├── 增量追加 v14.0
│   └── force_refresh=True      — 绕过缓存 + 与历史合并 + refresh=true/false 标记
├── 定时增量客户端 v15.0
│   └── cron_refresh.py         — 异步并发拉多 query，JSONL 输出，--loop 循环模式
├── OpenAI API v14.0
│   └── api_server.py           — FastAPI, 5 endpoints
│       ├── POST /v1/search     — 主搜索
│       ├── POST /v1/search/refresh — 增量追加
│       ├── GET  /v1/health
│       ├── GET  /v1/modes
│       └── GET  /v1/engines
├── 语言感知路由
│   ├── _has_chinese()          — CJK正则检测
│   ├── CN_ENGINES              — 中文引擎组
│   └── MODES                   — 7种模式（含 dev）
└── URL解析（Playwright跳转链）
    └── _resolve_results()      — 并发解析redirect URLs
```
