"""
star-search 答案生成 (LLM 总结)
v17.2: 把 8 条 search results 总结成 1 段答案 + 来源
- DeepSeek-V4-Flash via new-api (免费)
- 失败/超时降级返原始 results

环境变量 (可选, 默认 62.234.39.247:8080):
  LLM_BASE_URL  - LLM API base URL
  LLM_API_KEY   - LLM API key
  LLM_MODEL     - 模型名 (默认 DeepSeek-V4-Flash)
"""

import os
import json
import re
import time
import asyncio
import urllib.request
import urllib.error

# 加载多个可能的 key 源 (按优先级)
# 1) env var LLM_API_KEY
# 2) /home/ubuntu/star-search/.env (server-specific)
# 3) ~/.hermes/auth.json (local dev)
_NEWAPI_KEY = None

# 2) server .env
_env_path = os.path.expanduser("~/star-search/.env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("LLM_API_KEY=") and "=" in line:
                _NEWAPI_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

# 3) local ~/.hermes/auth.json
if not _NEWAPI_KEY:
    try:
        auth_path = os.path.expanduser("~/.hermes/auth.json")
        if os.path.exists(auth_path):
            with open(auth_path) as f:
                raw = f.read()
            m = re.search(r'sk-2ME[a-zA-Z0-9]+', raw)
            if m:
                _NEWAPI_KEY = m.group()
    except Exception:
        pass

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://62.234.39.247:8080/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", _NEWAPI_KEY or "")
LLM_MODEL = os.environ.get("LLM_MODEL", "DeepSeek-V4-Flash")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "15"))  # 答案生成 15s 上限

SYSTEM_PROMPT = """你是一个中文搜索引擎答案生成器, 风格类似 Perplexity AI.

输入: 用户 query + 8-10 条来自不同源(东方财富/新浪/雪球/IT之家/36kr/百度/搜狗等)的搜索结果.

输出要求:
1. 用 200-400 字中文给出直接答案 (3-5 句)
2. 数字答案要突出 (价格/数值/百分比)
3. 末尾列出 3-5 个来源域名, 格式: \\n\\n来源: domain1.com / domain2.com / domain3.com
4. 多个来源一致 → 直接给答案
5. 来源矛盾 → 列出分歧
6. 只基于提供的资料, 不要编造任何信息

⚠️ 重要诚实原则:
- 如果搜索结果是新闻/资讯/公告 (不是实时报价页), 不能编出具体价格数字
- 如果搜索结果没有具体的"当前股价 X 元", 应该说"实时股价请查询东方财富/新浪财经/同花顺等行情网站", 不要猜测
- 如果搜索结果是 5天/30天前的旧数据, 必须标注"截至 YYYY-MM-DD, ..."或"近期"
- 数字必须从源文 snippet 中能直接找到, 否则不写

财经 query 特殊处理:
- 股票 query → 优先找含"当前价/收盘/股价/涨幅"等词的源, 没有就告诉用户查行情网站
- 指数 query → 找具体点位, 没有就报"实时指数请查东方财富/新浪财经"
- 财报 query → 找具体数字, 没有就列已找到的关键数据

科技 query 特殊处理:
- 突出事实要点 (谁/什么/什么时候)
- 数字答案 (参数/价格/发布日期)

禁忌:
- 不要说"根据搜索结果"
- 不要说"以上信息仅供参考"
- 不要免责声明
- 不要编造任何源文没有的数字
- 直接给答案, 像 Perplexity 一样"""


def _extract_domain(url: str) -> str:
    """从 URL 提取干净域名"""
    if not url:
        return ""
    m = re.search(r'https?://(?:www\.|m\.)?([^/]+)', url)
    if m:
        return m.group(1)
    return ""


def _format_results_for_llm(results: list, max_n: int = 10) -> str:
    """把 results 格式化成 LLM 易读的文本"""
    lines = []
    for i, r in enumerate(results[:max_n], 1):
        title = r.get('title', '').strip()
        url = r.get('url', '').strip()
        snippet = r.get('snippet', '').strip() or r.get('desc', '').strip() or r.get('content', '').strip()
        engine = r.get('engine', '')
        domain = _extract_domain(url)
        lines.append(f"[{i}] {title}")
        if domain:
            lines.append(f"   来源: {domain}")
        if snippet:
            lines.append(f"   {snippet[:200]}")
        lines.append("")
    return "\n".join(lines)


async def generate_answer(query: str, results: list, mode: str = "deep") -> dict:
    """
    用 LLM 总结 search results 成一段答案

    Returns:
        {
            "answer": "比亚迪 94.78 元 (-2.05%)...\\n\\n来源: eastmoney.com / ...",
            "model": "DeepSeek-V4-Flash",
            "elapsed_ms": 2370,
            "tokens": 413,
            "sources": ["eastmoney.com", "sina.com.cn", "xueqiu.com"]
        }

    失败/超时: 返回 {"answer": None, "error": "..."}
    """
    if not results:
        return {"answer": None, "error": "no results to summarize"}

    if not LLM_API_KEY:
        return {"answer": None, "error": "LLM_API_KEY not configured"}

    formatted = _format_results_for_llm(results)

    # 提取来源域名 (去重)
    domains = []
    seen = set()
    for r in results[:8]:
        d = _extract_domain(r.get('url', ''))
        if d and d not in seen:
            seen.add(d)
            domains.append(d)

    # 调 LLM (异步, 避免阻塞)
    def _call_llm():
        req_data = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"query: {query}\n\n搜索结果:\n{formatted}"}
            ],
            "temperature": 0.3,
            "max_tokens": 400,
        }
        req = urllib.request.Request(
            f"{LLM_BASE_URL}/chat/completions",
            data=json.dumps(req_data).encode(),
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            return json.loads(resp.read())

    try:
        t0 = time.time()
        data = await asyncio.get_event_loop().run_in_executor(None, _call_llm)
        elapsed = time.time() - t0

        answer = data['choices'][0]['message']['content'].strip()
        usage = data.get('usage', {})

        # 验证: 如果 LLM 没自然包含来源, 追加
        if "来源" not in answer and domains:
            answer += f"\n\n来源: {' / '.join(domains[:5])}"

        return {
            "answer": answer,
            "model": LLM_MODEL,
            "elapsed_ms": int(elapsed * 1000),
            "tokens": usage.get('total_tokens', 0),
            "sources": domains[:5],
        }
    except urllib.error.URLError as e:
        return {"answer": None, "error": f"LLM timeout: {e}"}
    except Exception as e:
        return {"answer": None, "error": f"LLM error: {e}"}


# CLI 调试
if __name__ == "__main__":
    import sys
    test_results = [
        {"title": "比亚迪(002594)_最新价格_行情—东方财富网", "url": "https://quote.eastmoney.com/SZ002594.html", "snippet": "比亚迪 002594 最新价 94.78 (-2.05%)", "engine": "bing_cn"},
        {"title": "比亚迪94.78 (-2.05%)_新浪财经", "url": "https://finance.sina.com.cn/realstock/company/sz002594/nc.shtml", "snippet": "当前价 94.78 跌 2.05%", "engine": "bing_cn"},
    ]
    r = asyncio.run(generate_answer("比亚迪股价", test_results))
    print(json.dumps(r, ensure_ascii=False, indent=2))
