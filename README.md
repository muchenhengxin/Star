# star-search — 20.42 引擎中文 AI 搜索 + LLM 答案层

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/muchenhengxin/Star)
[![clawhub](https://img.shields.io/badge/clawhub-install-orange)](https://clawhub.ai/skill/star-search)
[![Version](https://img.shields.io/badge/version-20.42-blue)](https://clawhub.ai/skill/star-search)

> **免费中文搜索 API · 20.42 引擎混动 · 智能意图识别 · LLM 答案层 · MCP 协议**

为 AI Agent 提供实时中文搜索能力。对标 Tavily / Perplexity / Exa，**中文场景唯一可比产品**。

---

## ⚡ 5 分钟快速开始

### 方式 1: 一键安装（推荐）

```bash
# 1. 克隆
git clone https://github.com/muchenhengxin/Star.git
cd Star

# 2. 安装
bash install.sh

# 3. 编辑 .env 填入 LLM_API_KEY
nano .env

# 4. 启动
sudo systemctl start star-search

# 5. 测试
curl http://127.0.0.1:5000/v1/health
```

### 方式 2: clawhub 安装

```bash
clawhub install star-search
```

### 方式 3: Docker（推荐生产）

```bash
docker run -d -p 5000:5000 \
  -e LLM_API_KEY=sk-... \
  -e LLM_BASE_URL=https://api.openai.com/v1 \
  --name star-search \
  star-search:latest
```

---

## 🎯 集成示例

### LangChain

```python
from star_search_langchain import StarSearchTool

tool = StarSearchTool()
result = tool.run("华为 mate 70 价格", mode="quick", top=3)
```

### Dify

把 `dify_plugin/` 上传到 Dify Marketplace。

### 直接调用

```python
from star_search_langchain import search
result = search("华为 mate 70", mode="quick")
```

---

## 🔍 16 个搜索引擎

| 引擎 | 模式 | 速度 |
|---|---|---|
| 搜狗 HTTP | 中文快 | <1s |
| Bing CN | 中文 | <1s |
| GitHub Issues | 开发者 | <1s |
| 知乎 / 头条 / 微信 | 中文 | <2s |
| 百度 / 360 | 中文 | <2s |
| Bing 国际 | 英文 | <1s |
| RSS 23 个源 | 实时 | <1s |
| OpenAlex / CrossRef | 学术 | <1s |

---

## 🤖 4 种搜索模式

- `quick` - 仅搜索引擎（<2s）
- `deep` - 搜索引擎 + LLM 答案（<10s）
- `news` - 新闻优化（<1s）
- `policy` - 政策类（gov.cn / 新华网）
- `stock` - 财经实时报价
- `dev` - 开发者向（GitHub Issues 优先）
- `global` - 英文国际
- `auto` - 智能识别

---

## 📊 真实数据

- **2204 次 clawhub 下载**
- **16 引擎**
- **94.4% 意图识别准确率**
- **56.5% 实体识别准确率**
- **完全免费**

---

## 🔗 链接

- 公共 API: https://search.token-star.cn
- clawhub: https://clawhub.ai/skill/star-search
- GitHub: https://github.com/muchenhengxin/Star
- MCP 端点: https://search.token-star.cn/mcp/sse

---

## 许可证

MIT
