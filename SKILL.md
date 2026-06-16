---
name: star-search
description: "Use when asked to search the web, find online information, research topics, get news, look up Chinese content, or check A股/finance/tech news. **v20.9 — 速度/流式/多轮/稳定/学术/结构化/收藏/监控/i18n/MCP/语义搜索**! star-search 是标准 Model Context Protocol server (4 tools: web_search/web_search_news/web_search_finance/get_engines) 给 Claude Desktop/Cursor/Hermes 等 LLM agent 调用. 公网 HTTP/SSE: https://search.token-star.cn/mcp/sse . v20 实战 35-50: 速度优化 6s→0.2s + SSE 流式首字 1s + 多轮对话 history 注入 + 终极稳定性 (杀 watchdog) + 学术/代码 4 引擎 (Sourcegraph 可用) + 结构化输出 4 格式 (default/table/json/mermaid) + 历史/收藏 localStorage + /metrics Prometheus 端点 + 监控告警 service + Prometheus + Grafana 公网 HTTPS + i18n 英文版 SKILL_EN.md 22KB + BM25 语义搜索 5ms 5/5 query 命中. 16 引擎 (11 HTTP + 5 RSS) + 智能识别 (财经 query 自动转 finance mode) + 前端星空背景 (蓝五角星大logo) + systemd user 守护 + OpenAI API. 目标: 赶超百度搜索的免费中文搜索引擎 + LLM agent 实时事实层 (免费中文版 Tavily/Perplexity)."
version: 20.15.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Bing, Sogou, Baidu, 360, Weixin, Toutiao, Zhihu, GitHub, China, Hybrid, HTTP, Playwright, Chinese, Cache, API, OpenAI, Cron, Incremental, CSDN, Cnblogs, Eastmoney, CLS, Sina, Sohu, Quality, Explain, Debug, RSS, Ithome, 36kr, Sspai, Oschina, Woshipm, Global, Public, HTTPS, Frontend, SmartRouting, Finance, MCP, JSON-RPC, SSE, LLM-Answer, Perplexity-Mode, Honest-LLM, Honest-Search, v20, Speed-Optimization, Streaming, Multi-Turn, Monitoring, Prometheus, Grafana, Structured-Output, Favorites, Academic-Search, Code-Search]
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
---

# Star Search v20.6.0 — 速度/流式/多轮/稳定/学术/结构化/收藏/监控 一体化中文搜索 + LLM 答案

**一个脚本替代百度搜索 API + 答案 + 监控，免费、多引擎、高质量、可服务 subagent。**

> 本 skill 已从 v8.3 (Camofox) 演进到 v20.6.0 (HTTP+Playwright hybrid + 智能路由 + 公网 + LLM 答案 + SSE 流式 + 多轮 + Prometheus 监控)。**v16-v17 完整章节归档在 `references/v16-v17-legacy-archive.md`**。GitHub: https://github.com/muchenhengxin/Star @ commit 9e82976 (v20.6.0)。公网：https://search.token-star.cn (HSTS+LE证书+nginx 反代)。

---

## 🔥 v20.6.0 关键升级（实战 35-46 一次性打包）

| 实战 | 升级 | 价值 | 性能变化 |
|---|---|---|---|
| **35** | 速度优化（搜索层）| playwright 跳过 + 4s 顶层超时 + 缓存命中 | **6s → 0.2-1s** |
| **36** | SSE 流式输出 | `POST /v1/search/stream` + 5 事件 + 首字 < 1s | **首字响应 11s → < 1s** |
| **37** | 答案层提速 | `max_tokens=300` + `LLM_TIMEOUT=25s` | **7-8s 跑通** |
| **38-39** | 多轮对话 | `session_id` + `history` + localStorage | **6 轮上下文** |
| **40** | 终极稳定性 | 杀 `/tmp/watchdog.sh` 6/3 遗留 | **NRestarts=0** |
| **41-43** | 学术/代码 + 结构化 + 收藏 | 4 引擎 + 4 格式 + ⭐ 按钮 | **3 大新能力** |
| **44-46** | 监控 + Prometheus + Grafana | `/metrics` + 8 告警 + 11 panel dashboard | **公网 HTTPS** |

---

## 🏗️ 架构（v20.6）

```
[Browser] → https://search.token-star.cn:443
    ↓ (nginx + LE cert)
[/var/www/star-search/index.html]    ← 49KB 前端 (流式/收藏/历史/格式切换)
    ↓ (location /v1/ / /mcp/ / /v1/search/stream SSE)
[FastAPI 127.0.0.1:<api-port>]     ← api_server.py (systemd user)
    ├─ 16 engines (9 HTTP 启用 + 4 PW 跳过 + 3 cache)
    ├─ answer.py (GLM-4-Flash 总结, 诚实优先)
    ├─ metrics.py (Prometheus 指标, 14 个)
    ├─ academic_code.py (4 引擎)
    ↓
[LLM API: https://api.token-star.cn/v1]   ← GLM-4-Flash (永久免费)
[Prometheus + Grafana + node-exporter]     ← 9090/3000/9100 (公网 HTTPS)
[star-search-monitor.service]             ← 监控告警 (user systemd)
```

---

## 6 大能力模块（v20.6）

### 1. 速度与流式（实战 35-37）

- **搜索层 0.2-1s**：playwright 4 引擎跳过 + 4s 顶层超时 + 缓存命中 0ms
- **答案层 7-8s**：`max_tokens=300` + `LLM_TIMEOUT=25s` + 缓存 30min
- **SSE 流式**：`POST /v1/search/stream` 返回 5 事件（`search_start` / `search_done` / `answer_chunk×N` / `answer_done` / `done`）
- **首字响应 < 1s**：前端 fetch + ReadableStream 解析 SSE 逐字显示

### 2. 多轮对话（实战 38-39）

- **API 字段**：`session_id` + `history: [{q, a}, ...]`
- **后端**：`generate_answer(history)` 拼到 prompt（`=== 之前的对话 ===\n用户: ...\n助手: ...\n---`）
- **前端**：localStorage 存 `chat:{session_id}:history`（最近 20 轮）+ 左侧 session 列表

### 3. 终极稳定性（实战 40）

- **systemd 守护**：`stardust-svc.service` (user systemd + linger) + `Restart=always`
- **杀 6/3 遗留 watchdog**：`/tmp/watchdog.sh` 跑了 11 天误杀 39 次 → `kill -9` + `rm` 解决
- **uvicorn logging force=True**：避免 root logger 覆盖导致 detail.log 0 字节
- **实测**：7 query 跑 NRestarts=0 稳定

### 4. 学术 / 代码 / 结构化 / 收藏（实战 41-43）

- **学术/代码 4 引擎**：`google_scholar` / `semantic_scholar` / `grep_app` / `sourcegraph`（独立模块 `academic_code.py`）
  - 实际：1/4 可用（Sourcegraph；其他 3 个受 GFW / 限流 / 反爬限制）
- **结构化输出 4 格式**：`default` / `table` / `json` / `mermaid`（LLM 完全遵循）
  - Pydantic 避开 reserved name `format` → 改 `fmt`
  - cache key 含 `fmt`（4 格式独立缓存）
- **历史/收藏 UI**：顶栏 📚 历史 + ⭐ 收藏 2 按钮 + 每结果 ⭐ 按钮 + 弹层 + localStorage

### 5. 监控告警（实战 44-45）

- **`/metrics` 端点**：纯 Python 14 个指标（QPS / P99 / 缓存命中率 / 错误数 / LLM 时延）
- **`star-search-monitor.service`**：user systemd + linger + 3 告警规则 + 5min 摘要
- **告警规则**：错误率 > 20% / 缓存命中率 < 10% / 抓取失败 3 次

### 6. Prometheus + Grafana（实战 46）

- **3 个 docker 容器**：`star-prometheus` v2.54.1 (9090) / `star-grafana` v11.2.0 (3000) / `star-node-exporter` v1.8.2 (9100)
- **8 个告警规则**：错误率/缓存/服务挂/P99/CPU/内存/磁盘
- **Grafana 11 panel dashboard**：QPS / 缓存率 / 时延 / CPU / 内存 / 磁盘
- **公网 HTTPS**：`prom.token-star.cn` + `grafana.token-star.cn`（certbot + nginx 80/443 反代）

---

## 🚀 快速使用

### 1. Web UI（推荐，浏览器直接用）

```
https://search.token-star.cn
```

- 单查询 / 多轮对话 / SSE 流式 / 4 格式切换
- 顶部 📚 历史 + ⭐ 收藏
- 每个结果可 ⭐ 收藏
- 内嵌答案 AI 卡片 + 来源 chips + 引用 chip

### 2. API 端点

| 端点 | 用途 | 耗时 | 缓存 |
|---|---|---|---|
| `POST /v1/search` | 普通搜索 | 0.2-8s | 30min |
| `POST /v1/search/stream` | **SSE 流式** | 首字 < 1s | 30min |
| `POST /v1/answer` | 仅答案（自传 results）| 7s | 30min |
| `POST /v1/scholar` | 学术检索 | 4s | - |
| `POST /v1/code` | 代码检索 | 4s | - |
| `POST /v1/academic_mode` | 模式检测 | < 100ms | - |
| `GET /v1/health` | 健康检查 | < 10ms | - |
| `GET /v1/modes` | 列模式 | < 10ms | - |
| `GET /v1/engines` | 列引擎 | < 10ms | - |
| `GET /metrics` | Prometheus 指标 | < 100ms | - |
| `SSE /mcp/sse` | MCP server（4 tools）| - | - |
| `POST /mcp/messages` | MCP 客户端 | - | - |

### 3. CLI 模式

```bash
# 普通搜索
python3 search.py "AI大模型"                                # 中文→deep
python3 search.py "asyncio vs threading"                     # 英文→global
python3 search.py "今天股市情况"                              # v20 智能识别自动 finance
python3 search.py "华为鸿蒙" --mode deep --recency=week      # deep + 时效

# 结构化输出
python3 search.py "A股Top10" --format table
python3 search.py "MCP servers" --format json | jq .
python3 search.py "部署流程" --format mermaid

# 多轮
python3 search.py "比亚迪股价" --session mysession
python3 search.py "它和特斯拉比呢" --session mysession

# 收藏
python3 search.py "比亚迪股价" --star
```

### 4. MCP 接入（Claude Desktop / Cursor / Hermes / Cline / Continue）

#### 4.1 stdio 模式（本地，最简单）

**Claude Desktop 配置**：

```json
// macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
// Windows: %APPDATA%/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "star-search": {
      "command": "/usr/bin/python3",
      "args": ["/home/ubuntu/star-search/mcp/mcp_server.py"],
      "env": {
        "STAR_SEARCH_API": "http://127.0.0.1:5000/v1/search",
        "PYTHONPATH": "/home/ubuntu/.local/lib/python3.10/site-packages"
      }
    }
  }
}
```

**Hermes agent / Cursor / Cline**：

```json
{
  "mcpServers": {
    "star-search": {
      "command": "python3",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "STAR_SEARCH_API": "http://127.0.0.1:5000/v1/search"
      }
    }
  }
}
```

**关键**：
- `PYTHONPATH` 必须含 aiohttp 所在 venv 路径（本地开发要装 `pip install aiohttp`）
- `STAR_SEARCH_API` 指向你的 star-search API server（默认 `http://127.0.0.1:5000/v1/search`）
- 重启 Claude Desktop 生效

#### 4.2 SSE 公网模式（远程，跨设备）

**公网端点**：
```
Health: https://search.token-star.cn/mcp/health
SSE:    https://search.token-star.cn/mcp/sse
POST:   https://search.token-star.cn/mcp/messages?session_id=<从 SSE 推的 endpoint URL 拿>
```

**Python client 范例**：

```python
import aiohttp, json

async with aiohttp.ClientSession() as s:
    # 1. SSE 握手 - 服务端推 "event: endpoint\ndata: <URL>?session_id=XXX"
    async with s.get("https://search.token-star.cn/mcp/sse") as r:
        line = await r.content.readline()  # event: endpoint
        line = await r.content.readline()  # data: <URL>?session_id=XXX
        endpoint = line.decode().replace("data: ", "").strip()

    # 2. initialize
    req = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18"}
    }
    await s.post(endpoint, json=req)

    # 3. 读 SSE 响应拿 session_id
    # ...

    # 4. tools/call
    req = {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "web_search", "arguments": {"query": "比亚迪股价"}}
    }
    await s.post(messages_url, json=req)
```

**关键坑** — 客户端不要写死 session_id：
- **必须用 server 推的 session_id**（从 SSE endpoint URL 提取 `?session_id=XXX`）
- **不要** 自己生成 UUID
- 写死 → 必 400 `Invalid session_id`

#### 4.3 实测性能

| Tool | query | 耗时 | 结果 |
|---|---|---|---|
| `web_search` | "比亚迪股价" | 301ms | 8 条 (新浪/东财/知乎/investing/雪球/同花顺/9fzt) |
| `web_search_finance` | "上证指数今日收盘" | 870ms | 8 条 (4074.74 等) |
| `web_search_news` | "AI 创业" | 280ms | 8 条 IT之家科技新闻 |
| `get_engines` | - | <10ms | 16 引擎清单 |

#### 4.4 4 个 MCP Tools

| Tool | 用途 | 引擎 |
|---|---|---|
| `web_search` | 通用搜索（智能识别财经/英文/中文）| 默认 deep + 财经自动 finance |
| `web_search_news` | 科技/AI/产品新闻 | csdn/cnblogs + 5 RSS (ithome/36kr/sspai/oschina/woshipm) |
| `web_search_finance` | 财经/股票/A股专属 | eastmoney/cls/sina_finance/sohu/baidu/weixin/bing_cn |
| `get_engines` | 列 16 引擎 + 5 模式（agent 决策用）| - |

**LLM agent 调法**（Claude Desktop / Cursor）：
```
"帮我搜一下比亚迪股价，用 web_search 工具"
"用 web_search_finance 找上证指数"
"用 web_search_news 找今天 AI 创业新闻"
"列出所有引擎用 get_engines"
```

---

## 5. Plugins 商店集成（OpenAI GPT Actions + Anthropic Claude MCP）

### 5.1 OpenAI GPT Actions（ChatGPT Custom GPT）

**Auto-discover 端点**：`https://search.token-star.cn/.well-known/openapi.yaml`（OpenAPI 3.0 schema，11 个端点）

**GPT 编辑器配置步骤**：

1. 打开 [chatgpt.com](https://chatgpt.com) → Explore → Create a GPT
2. Configure → Actions → Create new action
3. Schema URL: `https://search.token-star.cn/.well-known/openapi.yaml`
4. Privacy policy: `https://github.com/muchenhengxin/Star/blob/main/LICENSE`
5. 保存

**聊天示例**：
```
"用 web_search 搜比亚迪股价"
"用 academicSearch 找 LLM 推理论文"
"用 discover 给我整理 Python 学习时间线"
"用 semanticSearch 找类似 'fastapi tutorial' 的结果"
```

**旧版 ChatGPT Plugins manifest**（`.well-known/ai-plugin.json`，向后兼容）—— 一些 ChatGPT 客户端仍支持。

### 5.2 Anthropic Claude MCP

**MCP server 注册**（Anthropic 官方 MCP registry）：

```bash
# 1. 部署 server (已就位): https://search.token-star.cn/mcp/sse
# 2. 提交到 https://github.com/modelcontextprotocol/servers (PR)
#    - 添加 entry 到 README.md servers table
#    - 文件: servers/star-search.json (mcp-server.json 复制)
# 3. Claude Desktop 自动从 registry discover (官方计划)
```

**MCP spec 文件**（`.well-known/mcp-server.json`，Anthropic 官方格式）—— 包含 4 tools 完整定义 + stdio/sse 双 transport + tags + 仓库链接。

### 5.3 Cursor / Cline / Continue

**MCP server 配置**（`~/.cursor/mcp.json` 或 settings）：

```json
{
  "mcpServers": {
    "star-search": {
      "command": "/usr/bin/python3",
      "args": ["/path/to/mcp_server.py"],
      "env": {"STAR_SEARCH_API": "http://127.0.0.1:5000/v1/search"}
    }
  }
}
```

**Cursor Chat 用法**：
```
"用 star-search 搜最新 AI 新闻"
"用 web_search_finance 找今天 A 股"
```

### 5.4 11 个端点完整列表

| 端点 | OpenAI operationId | MCP tool |
|---|---|---|
| `POST /v1/search` | `webSearch` | `web_search` |
| `POST /v1/search/refresh` | `webSearchRefresh` | - |
| `POST /v1/answer` | `generateAnswer` | - |
| `POST /v1/scholar` | `academicSearch` | - |
| `POST /v1/code` | `codeSearch` | - |
| `POST /v1/semantic_search` | `semanticSearch` | - |
| `POST /v1/discover` | `discover` | - |
| `GET /v1/engines` | `listEngines` | `get_engines` |
| `GET /v1/modes` | `listModes` | - |
| `GET /v1/health` | `health` | - |
| `SSE /mcp/sse` | - | `web_search_news` / `web_search_finance` |

### 5.5 提交检查清单

- [x] OpenAPI 3.0 schema (`.well-known/openapi.yaml`)
- [x] ai-plugin.json (`.well-known/ai-plugin.json`)
- [x] mcp-server.json (`.well-known/mcp-server.json`)
- [ ] GPT Store 公开提交 (需 ChatGPT Plus 账号创建 + 公开)
- [ ] MCP registry PR (modelcontextprotocol/servers)
- [ ] Cursor directory PR (cursor.com/directory)
- [ ] 提交后获取 install URL 加到 SKILL.md

---

## 📚 实战笔记（v20 实战 35-52）

### 搜索层

| 参数 | 默认 | 说明 |
|---|---|---|
| `--mode` | `auto` | deep / quick / news / dev / global / finance / auto |
| `--engine` | 自动 | 单引擎指定（sogou / baidu / weixin / ...）|
| `--top` | 10 | 输出数量（最大 30）|
| `--recency` | 无 | day / week / month / year |
| `--exact` | False | 精确匹配 |
| `--sources` | 无 | 限定来源（weixin,baidu,...）|
| `--format` | `default` | `default` / `table` / `json` / `mermaid` |
| `--star` | False | 收藏到 localStorage |
| `--session` | 自动生成 | 多轮对话 session_id |

### 答案层

| 参数 | 默认 | 说明 |
|---|---|---|
| `--answer` | True | 是否生成 LLM 答案 |
| `LLM_MODEL` | `glm-4-flash` | LLM 模型（GLM-4-Flash 永久免费）|
| `LLM_TIMEOUT` | 25 | 答案超时（秒）|
| `max_tokens` | 300 | 答案长度（GLM-4 不严格遵守）|
| `ANSWER_CACHE_TTL` | 1800 | 答案缓存 TTL（秒）|

### 监控层

| 指标 | 类型 | 说明 |
|---|---|---|
| `star_search_requests_total` | counter | 请求数（按 endpoint 分）|
| `star_search_request_errors_total` | counter | 错误数 |
| `star_search_search_total` | counter | 搜索数 |
| `star_search_cache_hit_rate` | gauge | 缓存命中率（0-1）|
| `star_search_search_latency_ms` | histogram | 搜索 P50/P95/P99 |
| `star_search_answer_latency_ms` | histogram | 答案 P50/P95/P99 |
| `star_search_llm_latency_ms` | histogram | LLM P50/P95/P99 |

---

## 📦 部署

### 1. systemd user（推荐）

```ini
# ~/.config/systemd/user/stardust-svc.service
[Unit]
Description=star-search API + monitor
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/star-search
ExecStart=/usr/bin/python3 scripts/api_server.py --host 127.0.0.1 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
loginctl enable-linger ubuntu  # 开机自启 + 登出自启
systemctl --user enable --now stardust-svc.service
```

### 2. Prometheus + Grafana

```bash
cd /home/ubuntu/docker
docker compose -f prometheus-grafana-stack.yml up -d
```

### 3. 公网 HTTPS

```bash
# DNSPod A 记录
prom.token-star.cn   → <服务器IP>
grafana.token-star.cn → <服务器IP>

# certbot SSL
certbot --nginx -d prom.token-star.cn -d grafana.token-star.cn \
  --non-interactive --agree-tos -m <your-email>
```

---

## 🔌 依赖

```bash
pip install aiohttp beautifulsoup4 lxml playwright fastapi uvicorn 'pydantic>=2' httpx requests
playwright install chromium  # 可选 (v20 实战 35 跳过)
```

无需 API Key、无需登录、无需付费（GLM-4-Flash 走 `api.token-star.cn/v1` 永久免费）。

---

## ⚠️ 已知陷阱（v20 实战 35-46 总结）

### v20.1 速度优化（实战 35）

- **playwright 拖 15-20s** → 4 引擎跳过
- **aiohttp 单引擎 4s timeout** + 顶层 4s 强制截止
- **try/except 降级**到缓存命中

### v20.2 SSE 流式（实战 36）

- **f-string 大坑**：`"event: done\ndata: {}\n\n"` 空 `{}` 报 SyntaxError
- **nginx 必须**：`proxy_buffering off` + `proxy_read_timeout 60s` + `proxy_http_version 1.1`

### v20.3 答案层提速（实战 37）

- **max_tokens 600 → 300**：GLM-4-Flash 46 tok/s × 300 = 6.5s 实际（设 600 实际 947 tokens）
- **LLM_TIMEOUT 8 → 12 → 25**：复杂格式（json/mermaid）需要 25s buffer

### v20.4-5 多轮对话 + 稳定性（实战 38-40）

- **NRestarts 涨必查真凶**：实战 40 watchdog.sh 6/3 遗留 11 天误杀 39 次
- **uvicorn logging 必须 force=True**：避免 root logger 覆盖导致 detail.log 0 字节
- **cache key 不含 history**：命中率 30-50%（vs 80% 包含 history）

### v20.6 学术/结构化/收藏（实战 41-43）

- **Pydantic 避开 reserved name**：`format` 是 reserved → 改 `fmt`
- **新参数要全链路 grep**：实战 42 `/v1/search` 加 fmt 但 `/v1/search/stream` 没加 → 6 调试
- **cache key 必含变化因子**：cache key 漏 fmt → 4 格式命中同缓存
- **GFW 环境下外部 API 受限是常态**：实战 41 4 引擎只 1 个能用

### v20.7 监控告警（实战 44-46）

- **docker 容器 mount data 目录**：`user:"0"` + `chmod 777` 解决 mmap 权限
- **docker 镜像加速**：Docker Hub 直连 timeout → `daemon.json` 加 `daemonocloud.io`
- **腾讯云防火墙**：只开 22/80/443（直接开 9090/3000 不行，走 nginx 反代）
- **DNSPod A 记录必备**：不加点不生效

---

## 📁 文件结构（v20.6）

```
star-search/
├── SKILL.md                      # 本文件 (v20.6.0)
├── index.html                    # v20.6 前端 (49KB, 多轮/收藏/格式切换)
├── README.md                     # GitHub README
├── search.py                     # v20.6 主搜索 (16 引擎 + 速度优化)
├── answer.py                     # v20.6 答案层 (GLM-4 + 4 格式 + 引用 + 多轮)
├── api_server.py                 # v20.6 API server (SSE + 多端点)
├── academic_code.py              # v20.6 学术/代码 4 引擎
├── metrics.py                    # v20.6 Prometheus 指标 (14 个)
├── mcp_server.py                 # v20.6 MCP server (4 tools)
├── mcp_*.py                      # v20.6 MCP 客户端
├── scripts/
│   ├── cron_refresh.py           # 定时增量客户端
│   ├── deploy_web.sh             # nginx 部署
│   ├── star_search_monitor.py    # v20.6 监控告警 service
│   └── ...
├── references/
│   ├── v16-v17-legacy-archive.md       # v16-v17 完整章节归档
│   ├── v16-finance-mode-and-smart-routing.md
│   ├── v16-public-deployment-and-daemon.md
│   ├── v17-frontend-answer-card.md
│   ├── v17-llm-answer-quality-strategy.md
│   ├── mcp-server-zero-deps.md
│   ├── site-bing-proxy-pattern.md
│   ├── incremental-cache-pattern.md
│   └── llm-answer-honest-prompt.md
├── /etc/systemd/user/stardust-svc.service   # systemd unit
├── /etc/nginx/sites-enabled/search-token-star.conf
├── /var/www/star-search/index.html
├── /home/ubuntu/docker/prometheus-grafana-stack.yml
└── /home/ubuntu/star-search/.env
    LLM_BASE_URL=https://api.token-star.cn/v1
    LLM_MODEL=glm-4-flash
    LLM_TIMEOUT=25
    ANSWER_CACHE_TTL=1800
```

---

## 🔄 版本历史

| 版本 | 日期 | 主要变更 |
|---|---|---|
| **v20.15.0** | 2026-06-16 | **实战 55：用户系统**（手机号注册/登录 + HMAC token 12h + JSON users.json + quota 100/天 + 4 端点 /v1/auth/{register,login,me,quota} + Authorization Bearer quota check）|
| v17.7.0 | 2026-06-04 | 答案缓存（236x speedup）+ 内联引用（Perplexity Mode 完整体验）|
| v17.5.0 | 2026-06-04 | 4 类 Prompt 模板（finance/tech/news/general）|
| v17.4.0 | 2026-06-04 | 多轮相关问题（3 个 followup chips）|
| v17.3.0 | 2026-06-04 | 前端 AI 答案卡片（Perplexity Mode UI）|
| v17.2.0 | 2026-06-03 | LLM 答案层（GLM-4-Flash 永久免费）|
| v17.0.0 | 2026-06-03 | **MCP 化**：4 tools（web_search / web_search_news / web_search_finance / get_engines）|
| v16.2.5 | 2026-06-03 | finance 引擎修中文财经搜索结果 |
| v16.2.4 | 2026-06-03 | 星空背景 + 大字 logo + 蓝五角星 |
| v16.2.3 | 2026-06-03 | logo 升级 + SKILL.md 加 references |
| v16.2.2 | 2026-06-03 | 公网前端 + 财经智能识别 + Playwright 优雅降级 |
| v16.2.1 | 2026-06-03 | 公网 HTTPS + 前端文人风 + 守护进程 |
| v16.2 | 2026-06-03 | Playwright 优雅降级（无 sudo 也能跑）|
| v16.1 | 2026-06-02 | +5 RSS 引擎 + global 中英双源 + finance mode |
| v16.0 | 2026-06-02 | sogou KeyError 修复 + 质量标识 🌟🌟🌟 + --explain |
| v15.1 | 2026-06-01 | +7 site:bing 代理引擎（csdn/cnblogs/eastmoney/cls/...）|
| v15.0 | 2026-06-01 | 10 引擎直搜 + 定时增量：toutiao/zhihu/weixin |
| v14.0 | 2026-06-01 | OpenAI API + 增量追加 |
| v13.0 | 2026-06-01 | 智能缓存层（分桶 TTL + query 归一化）|
| v12.2 | 2026-06-01 | 智能去重 + ⭐ 跨源标记 |
| v8.3 | 2026-05-10 | 旗舰版（Camofox 时代，已废弃）|

完整 v16-v17 章节见 `references/v16-v17-legacy-archive.md`。

---

## 📚 实战笔记（v20 实战 35-54）

实战 54 移动端 UI 优化：viewport viewport-fit=cover + input type=search/inputmode/enterkeyhint (iOS 搜索键) + iOS safe area inset (刘海屏) + tap highlight 禁用 + touch-action manipulation + 响应式字号 (768px / 480px 断点) + body overscroll-behavior: contain + 长按选择禁用。

实战 53 PWA (Progressive Web App)：manifest.webmanifest + service-worker.js 离线缓存 + icon-192/512 PNG (Python 手写 zlib) + iOS meta tags + 公网 HTTPS 一键安装到主屏 (0 审核 0 费用 4 平台通用)。

实战 52 P3-24 OpenAI/Anthropic plugins 商店（OpenAPI 3.0 schema for GPT Actions + ai-plugin.json for ChatGPT legacy + mcp-server.json for Anthropic MCP registry，3 个 manifest 在 `.well-known/` 目录）。

实战 51 P3-23 Perplexity 探索发现（3 mode: timeline/comparison/related + 修 LLM 答案层真 key + subprocess runner 解 uvloop 冲突）。

实战 50 P3-22 Vector DB 语义搜索（BM25 + 字符 n-gram 中文友好 + 内存索引 + 5ms 检索）。

实战 49 加 i18n 英文版（`SKILL_EN.md` 22KB / 完整翻译 v20.7 全部能力）。

以下是实战过程的详细笔记，对应每个升级的 troubleshooting 路径。


---


## v20.1 实战 35 速度优化 (6s → 0.2-1s)
- playwright 4 引擎跳过 (拖 15-20s)
- aiohttp 单引擎 4s timeout + 顶层 4s 强制截止
- try/except 降级到缓存命中
- 缓存 30min (query 归一化 + n_results bucket)
- 实测: 缓存命中 0ms / 未命中 1-4s (搜) + 6-7s (答) = 7-8s

## v20.2 实战 36 SSE 流式输出 (首字 < 1s)
- 新端点 `POST /v1/search/stream` (不动老 `/v1/search`)
- 5 事件: search_start / search_done / answer_chunk×N / answer_done / done
- nginx `proxy_buffering off` + `proxy_read_timeout 60s` 必备
- 前端 fetch + ReadableStream 解析 SSE 逐字显示
- f-string 大坑: `{}` 空表达式报 SyntaxError, 改 `"event: done\ndata: {}\n\n"`

## v20.3 实战 37 答案层提速
- max_tokens 600 → 300 (GLM-4-Flash 46 tok/s × 300 = 6.5s 实际)
- LLM_TIMEOUT 15s → 12s → 25s (复杂格式需要 25s buffer)
- 实际 7-8s 跑通

## v20.4 实战 38-39 多轮对话
- api_server SearchRequest 加 `session_id` + `history: list`
- answer.py `generate_answer(history)` 拼 prompt (`=== 之前的对话 ===\n用户: ...\n助手: ...\n---`)
- 前端 localStorage 存 `chat:{session_id}:history` (最近 20 轮)
- 左侧 session 栏 (切换/重命名/删除)
- cache key 不含 history (命中率 30-50%)

## v20.5 实战 40 终极稳定性 (杀 watchdog)
- NRestarts 持续涨 + syslog 30-33s 周期 SIGKILL
- 调试 4 步: detail.log (force=True) → uvicorn 覆盖 root logger → syslog 找元凶 → 找到 `bash /tmp/watchdog.sh` (6/3 部署遗留跑了 11 天)
- 修: `kill -9 13296` + `rm /tmp/watchdog.sh /tmp/qs.sh`
- 7 query 跑 NRestarts=0 稳定

## v20.6 实战 41-43 学术/结构化/收藏
- **学术/代码** (4 引擎 + 2 端点 + academic_code.py 独立模块): scholar / semantic_scholar / grep_app / sourcegraph → 实际只 Sourcegraph 可用 (GFW + 限流 + 反爬)
- **结构化输出 4 格式**: `default` / `table` / `json` / `mermaid` — LLM 完全遵循
- **Pydantic 避开 reserved name**: `format` 改 `fmt`
- **新参数要全链路 grep**: `/v1/search` 加 fmt 但 `/v1/search/stream` 没加 → 6 调试
- **cache key 必含变化因子**: 实战 42 cache key 不含 fmt → 4 格式命中同缓存
- **历史/收藏 UI**: 顶栏 📚 + ⭐ 2 按钮 + 每结果 ⭐ 按钮 + 弹层 + localStorage

## v20.7 实战 44-46 监控告警 + Prometheus + Grafana
- **/metrics 端点**: 纯 Python 14 个指标 (无 prometheus_client 依赖)
- **MetricsMiddleware**: 自动计 endpoint + 错误
- **监控 service**: star-search-monitor.service (user systemd + linger) + 3 告警规则 + 5min 摘要
- **Prometheus 2.54.1 + Grafana 11.2.0 + node-exporter 1.8.2** (docker compose 3 容器, 9090/3000/9100)
- **8 个告警规则** (错误率/缓存/服务挂/P99/CPU/内存/磁盘)
- **Grafana 11 panel dashboard** (QPS/缓存/时延/CPU/内存)
- **公网 HTTPS**: prom.token-star.cn + grafana.token-star.cn (certbot + nginx 80/443 反代)
- **DNSPod A 记录必备** + 腾讯云防火墙只开 22/80/443 (直接开 9090/3000 不行, 走 nginx 反代)

## v20 通用教训 (实战 35-46 总结)
- **不要假设"接了就能用"**: 实战 41 4 引擎只 1 个能用 (GFW + 限流 + 反爬)
- **新参数要全链路 grep**: 实战 42 fmt 跨多个端点
- **cache key 必含所有变化因子**: cache key 漏 fmt / history / mode 都会错乱
- **Pydantic 避开 reserved name**: `format` 是 reserved, 改 `fmt`
- **NRestarts 涨必查真凶**: 实战 40 watchdog 6/3 遗留 11 天误杀 39 次
- **调试时 detail.log 必须可写**: uvicorn 覆盖 root logger → `force=True` 修
- **docker 容器 mount data 目录**: `user:"0"` + chmod 777 解决 mmap 权限
- **docker 镜像加速**: Docker Hub 直连 timeout → daemon.json 加 daemonocloud.io


