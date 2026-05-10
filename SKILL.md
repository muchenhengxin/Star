---
name: star-search
description: "Use when asked to search the web, find online information, research topics, get news, or look up content. Primary: Sogou+Camofox (10 results, no captcha). Backup: Baidu+Camofox (9 results, random captcha). 360+Camofox (6 results, no captcha). All via Camofox REST API only — NOT Hermes browser tools."
version: 8.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Sogou, Baidu, 360, Camofox, China, Research, Discovery]
    related_skills: [arxiv, blogwatcher, session_search]
    references:
      - camofox-api.md
---

# Star Search v8.3 — 五维旗舰版（替代百度搜索）

**一个脚本替代百度搜索API，免费、多引擎、高质量。**

`search.py` 通过 Camofox REST API 并行调用搜狗+百度+360三引擎，自动去重排序、提取摘要日期、交叉验证，最终聚合为一份高质量的搜索结果。

> **目标**：全面替代 `baidu-search__web_search`（百度搜索工具），省下百度API费用，同时获得更好的结果质量。

---

## 🔥 核心能力

### 五维指标（2026-05-10实测）

| 维度 | v8.3 表现 | 与百度搜索工具对比 |
|:----|:---------|:----------------|
| **全面性** | 25-29条/次（三引擎聚合） | ✅ **超过**（百度20条/次） |
| **准确性** | 100%有摘要（平均90字） | ✅ **超过**（百度稳定20-50字） |
| **时效性** | 60-100%有日期标记 📅 | ✅ **超过**（百度无法自动标注日期） |
| **稳定性** | 三引擎互为fallback（验证码自动降权） | ✅ **超过**（单点依赖百度API） |
| **速度** | deep 3.5-4.5秒 / quick 2.5秒 | ⚠️ 略慢（百度1-2秒） |
| **成本** | **免费** | ✅ **完全替代**（百度API按量付费） |
| **直接URL** | 自动解析top搜狗短链为真实URL | ⚠️ 默认90%为跳转链（建议`--json`模式使用） |

### v8.3 新特性一览

| 特性 | 说明 |
|------|------|
| **三引擎并行** | 搜狗+百度+360同时搜索，自动去重 |
| **摘要覆盖率100%** | v2提取器全区域扫描，平均90字长摘要 |
| **日期提取** | 从标题中自动解析发布时间 |
| **交叉验证标记⭐** | 多引擎同标题自动标注 |
| **智能去重+排序** | 时间因子+引擎权重综合排序 |
| **5种搜索模式** | policy/news/deep/quick/stock + auto自动检测 |
| **URL自动解析** | 默认解析top搜狗短链为真实URL |
| **百度验证码自适应** | 检测到验证码自动跳过，不影响结果 |
| **JSON输出分离** | info走stderr，结果走stdout，管道解析零干扰 |

---

## 🚀 快速使用

```bash
# 最简单的搜索（deep模式，自动选引擎）
python3 search.py "存储芯片超级周期"

# 指定模式
python3 search.py "A股半导体" --mode stock

# JSON输出（推荐给子代理/脚本使用）
python3 search.py "AI Agent 2026" --mode news --json

# 单引擎指定
python3 search.py "国务院政策" --engine baidu

# 列出可用引擎和模式
python3 search.py --list
```

### 五种搜索模式

| 模式 | 命令 | 引擎 | 适用场景 |
|------|------|------|----------|
| **深度研究** | `--mode deep` | 搜狗+百度+360 | 综合研究，最大覆盖 |
| **快速查询** | `--mode quick` | 仅搜狗 | 快速验证，最快返回 |
| **政策研究** | `--mode policy` | 百度+搜狗(权重重配) | 政策/法规类搜索 |
| **新闻追踪** | `--mode news` | 搜狗+百度 | 最新动态 |
| **股票行情** | `--mode stock` | 搜狗+百度(强权重) | 股票/财经查询 |

**自动模式（默认）**：根据查询关键词自动匹配模式
- `政策/国务院/央行` → policy
- `股票/股价/涨停/代码` → stock
- `今日/最新/快讯` → news
- 其他 → deep

### JSON输出（推荐子代理使用）

```bash
# 子代理通过管道获取结构化结果
python3 search.py "DeepSeek 融资 2026" --mode news --json | python3 -c "
import json,sys
data = json.load(sys.stdin)
for r in data:
    print(f\"[{r['engine']}] {r['title']} | {r['date']} | 摘要:{r['summary'][:30]}\")
"
```

**JSON输出字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 结果标题 |
| `url` | string | URL（搜狗短链已自动解析为真实URL，360短链保持原样） |
| `url_type` | string | `direct`（可直接访问）或 `redirect`（跳转链） |
| `engine` | string | 来源引擎：sogou/baidu/360 |
| `cross_validated` | int | 被几个引擎收录（≥2时代表交叉验证） |
| `date` | string | 发布日期（可能为空） |
| `summary` | string | 摘要（平均90字） |
| `score` | float | 综合评分 |
| `resolved` | bool | URL是否已解析为真实地址 |

---

## ⚙️ 搜索模式参数（高级）

每种模式可自定义引擎组合、权重和参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--engine sogou` | 自动 | 指定单个引擎 |
| `--mode deep` | auto | 搜索模式 |
| `--json` | 否 | JSON结构化输出 |
| `--top 10` | 10 | 输出结果数量（最大30） |
| `--list` | 否 | 列出可用引擎和模式 |

---

## 📊 性能基准

| 模式 | 耗时 | 结果数 | 直接URL |
|------|------|--------|---------|
| deep（三引擎） | 3.5-4.5秒 | 25-29条 | 前4-5条解析为真实URL |
| quick（单搜狗） | 2.5-3.5秒 | 6-7条 | 前2条解析为真实URL |
| policy | 3-4秒 | 15-20条 | 前4-5条 |
| news | 3-4秒 | 15-20条 | 前4-5条 |
| stock | 3-4秒 | 15-20条 | 前4-5条 |

---

## 🔌 依赖与环境

### 必要组件

- **Python 3.8+**
- **Camofox 服务**（运行在 localhost:9377）
- 无需API Key，无需付费

### Camofox 启动

```bash
# 验证Camofox是否运行
curl http://localhost:9377/health
# 正常返回: {"ok":true,"browserConnected":true,"engine":"camoufox"}
```

如未运行，安装启动：

```bash
cd /path/to/camofox-browser && npm start &
```

### 配置参数

`search.py` 头部可调整的关键参数：

```python
CAMOUFOX_URL = "http://localhost:9377"   # Camofox服务地址
USER_ID = "star-search"                   # Camofox用户ID
PARALLEL_TIMEOUT = 25                     # 搜索超时（秒）
```

---

## ⚠️ 已知限制

1. **360短链**：`so.com/link?m=xxx` 同样为JS跳转链，`--json`输出中保持 `url_type: "redirect"`
2. **速度**：多引擎并行+URL解析导致比百度搜索工具慢1-2秒
3. **百度验证码**：偶发，代码已自动处理（跳过百度结果，不影响其他引擎）
4. **Camofox未启动**：搜索会立即报错退出

---

## 🔄 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 8.3 | 2026-05-10 | **旗舰版**：URL异步解析、摘要100%覆盖、JSON输出分离、验证码自适应 |
| 8.2 | 2026-05-09 | 标题时间戳、URL短链解析、并行去重、5种模式引擎权重 |
| 8.1 | 2026-05-09 | 动态权重、时间因子排序、搜索模式预设 |
| 8.0 | 2026-05-08 | 搜狗+百度+360多引擎并行，智能去重排序 |
| 7.x | 2026-04 | 单引擎版本，Camofox REST API基础实现 |

---

## 📁 文件结构

```
skills/star-search/
├── search.py          # 主程序（1047行，v8.3）
├── SKILL.md           # 本文件
└── camofox-api.md     # Camofox API快速参考
```

---

## 📝 使用建议

| 使用场景 | 推荐方式 |
|----------|----------|
| **日常信息收集** | `--mode deep`（默认） |
| **验证某个事实** | `--mode quick` |
| **研究政策/法规** | `--mode policy` |
| **追踪最新动态** | `--mode news` |
| **查询股票行情** | `--mode stock` |
| **子代理调用** | `--mode news --json`（管道解析） |
| **彻底替代百度搜索** | 全局配置中设置 `star-search` 为首选搜索skill |

---

> **下一步**：发布到 ClawHub / GitHub。
