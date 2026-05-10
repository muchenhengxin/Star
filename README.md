# Star Search v8.3 — 多引擎中文搜索旗舰版

> **免费替代百度搜索API。三引擎并行搜狗+百度+360，自动去重排序，100%摘要覆盖，真实URL解析。**

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue) ![License MIT](https://img.shields.io/badge/license-MIT-green) ![Version 8.3](https://img.shields.io/badge/version-8.3.0-orange)

---

## 为什么需要 Star Search？

百度搜索API（Baidu Search API）按量付费，每次搜索调用ChatGPT成本不低。Star Search 通过 Camofox 反检测浏览器实现**免费、多引擎、高质量**的中文搜索，五维指标全面超越百度搜索API。

| 维度 | Star Search v8.3 | 百度搜索API | 对比 |
|:----|:----------------|:-----------|:----:|
| 结果数 | 25-29条/次 | 20条/次 | ✅ **超过** |
| 来源多样性 | 搜狗+百度+360 | 仅百度 | ✅ **远超** |
| 摘要覆盖率 | 100%（平均90字） | 稳定20-50字 | ✅ **超过** |
| 时效性 | 60-100%有日期标记 | 无日期标签 | ✅ **超过** |
| 稳定性 | 三引擎互为fallback | 单点依赖 | ✅ **超过** |
| 成本 | **免费** | 按量付费 | ✅ **完全替代** |
| 速度 | 3.5秒（三引擎含URL解析） | 1-2秒 | ⚠️ 略慢 |
| 直接URL占比 | 默认解析top 5条 | 100%真实URL | ⚠️ 略差（360补充引擎无法解析） |

---

## 快速开始

```bash
# 搜索
python3 search.py "存储芯片超级周期"

# 指定模式
python3 search.py "A股半导体" --mode stock

# JSON输出（推荐脚本/子代理使用）
python3 search.py "AI Agent" --mode news --json

# 列出可用引擎和模式
python3 search.py --list
```

**前置依赖：** Camofox 服务运行在 `http://localhost:9377`

```bash
# 验证Camofox
curl http://localhost:9377/health
# ✓ 正常: {"ok":true,"browserConnected":true}
```

---

## 五种搜索模式

| 模式 | 命令 | 引擎 | 场景 |
|------|------|------|------|
| **深度研究** | `--mode deep` | 搜狗+百度+360 | 综合研究，最大覆盖 |
| **快速查询** | `--mode quick` | 仅搜狗 | 快速验证 |
| **政策研究** | `--mode policy` | 百度+搜狗(重配权重) | 政策法规 |
| **新闻追踪** | `--mode news` | 搜狗+百度 | 最新动态 |
| **股票行情** | `--mode stock` | 搜狗+百度(强权重) | 股票财经 |

默认 `auto` 模式根据关键词自动匹配。

---

## JSON 输出格式

```json
[
  {
    "title": "存储芯片迎超级周期：全球龙头股价创新高",
    "url": "https://stock.10jqka.com.cn/20260507/c676512445.shtml",
    "url_type": "direct",
    "engine": "sogou",
    "cross_validated": 2,
    "date": "2026-05-07",
    "summary": "机构人士认为，在AI算力需求持续爆发下...存储板块强势行情有望延续。",
    "score": 183.0,
    "resolved": true
  }
]
```

各字段含义：
- `title` — 结果标题
- `url` — URL（搜狗短链已自动解析为真实地址）
- `url_type` — `direct`（可直达）/ `redirect`（跳转链）
- `engine` — 来源引擎：sogou / baidu / 360
- `cross_validated` — 被几个引擎同时收录
- `date` — 发布日期
- `summary` — 摘要（平均90字）
- `score` — 综合评分
- `resolved` — URL是否解析为真实地址

---

## 性能基准

| 模式 | 耗时 | 结果数 | 真实URL |
|------|------|--------|---------|
| deep（三引擎） | 3.5-4.5秒 | 25-29条 | 前5条 |
| quick（单搜狗） | 2.5-3.5秒 | 6-7条 | 前2条 |
| policy | 3-4秒 | 15-20条 | 前5条 |
| news | 3-4秒 | 15-20条 | 前5条 |
| stock | 3-4秒 | 15-20条 | 前5条 |

---

## v8.3 新特性

| 特性 | 状态 | 说明 |
|------|------|------|
| **三引擎并行** | ✅ | 搜狗+百度+360同时搜索，2-3秒返回 |
| **摘要100%覆盖** | ✅ | v2提取器全区域扫描，平均90字 |
| **日期提取** | ✅ | 标题内日期解析，60-100%结果有日期 |
| **交叉验证标记⭐** | ✅ | 多引擎同标题自动标注 |
| **URL自动解析** | ✅ | 默认解析top搜狗短链为真实URL |
| **JSON输出分离** | ✅ | info走stderr，结果走stdout，管道无干扰 |
| **百度验证码自适应** | ✅ | 检测验证码自动跳过 |
| **5种搜索模式** | ✅ | policy/news/deep/quick/stock + auto |

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 8.3 | 2026-05-10 | **旗舰版**：URL异步解析、摘要100%覆盖、JSON输出分离、验证码自适应 |
| 8.2 | 2026-05-09 | 标题时间戳、URL短链解析、并行去重、5种模式引擎权重 |
| 8.1 | 2026-05-09 | 动态权重、时间因子排序、搜索模式预设 |
| 8.0 | 2026-05-08 | 搜狗+百度+360多引擎并行，智能去重排序 |

---

## 技术架构

```
用户搜索请求 → search.py
                    ↓
            ThreadPoolExecutor
           /        |        \
      搜狗搜索   百度搜索   360搜索
      (Camofox) (Camofox) (Camofox)
           \        |        /
            ParallelSearch
                    ↓
            deduplicate + rank
            (时间因子 + 交叉验证)
                    ↓
            URL解析（后台异步）
                    ↓
            stdout输出（文本/JSON）
```

---

## 依赖

- Python 3.8+
- Camofox 服务（`http://localhost:9377`）
- 无需 API Key

---

## License

MIT
