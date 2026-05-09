#!/usr/bin/env python3
"""
Star Search v8 - 多引擎智能搜索（搜狗优先）

引擎优先级: 搜狗(主) → 百度(备) → 360(备备)

使用方法:
    python3 search.py "关键词"
    python3 search.py "关键词" --engine baidu
    python3 search.py "关键词" --json
"""

import json
import subprocess
import re
import time
import argparse
import sys
from urllib.parse import quote

CAMOUFOX_URL = "http://localhost:9377"
USER_ID = "star-search"

# 引擎配置（按优先级排序）
ENGINES = [
    {
        "id": "sogou",
        "name": "搜狗搜索",
        "url_template": "https://www.sogou.com/web?query={q}&ie=utf8",
        "weight": 100,  # 最高权重
    },
    {
        "id": "baidu",
        "name": "百度搜索",
        "url_template": "https://www.baidu.com/s?wd={q}",
        "weight": 60,
    },
    {
        "id": "360",
        "name": "360搜索",
        "url_template": "https://www.so.com/s?q={q}",
        "weight": 30,
    },
]


def create_tab(url: str) -> str:
    """创建 tab 并导航到 URL"""
    payload = json.dumps({
        "userId": USER_ID,
        "sessionKey": f"search-{int(time.time())}",
        "url": url
    })
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{CAMOUFOX_URL}/tabs",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True
    )
    data = json.loads(r.stdout)
    if "error" in data:
        raise Exception(f"Tab creation failed: {data['error']}")
    return data["tabId"]


def get_snapshot(tab_id: str) -> str:
    """获取页面快照"""
    r = subprocess.run(
        ["curl", "-s", f"{CAMOUFOX_URL}/tabs/{tab_id}/snapshot?userId={USER_ID}"],
        capture_output=True, text=True
    )
    data = json.loads(r.stdout)
    if isinstance(data, dict):
        return data.get("snapshot", "")
    return r.stdout


def extract_sogou(snapshot: str) -> list:
    """提取搜狗搜索结果"""
    # 搜狗结构: heading "标题" [level=3]: → link → /url: /link?url=XXX
    results = []
    # 匹配 heading 及其后的 url
    pattern = r'heading "([^"]+)" \[level=3\]:.*?/url: (/link\?url=[^\s\\]+)'
    matches = re.findall(pattern, snapshot, re.DOTALL)
    for title, path in matches:
        title = title.strip()
        if len(title) > 5:
            results.append({
                "title": title,
                "url": f"https://www.sogou.com{path}",
                "engine": "sogou"
            })
    return results


def extract_baidu(snapshot: str) -> list:
    """提取百度搜索结果"""
    results = []
    pattern = r'heading "([^"]+)" \[level=3\]:.*?/url: (http://www\.baidu\.com/link\?url=[^\s\\]+)'
    matches = re.findall(pattern, snapshot, re.DOTALL)
    for title, url in matches:
        title = title.strip()
        if len(title) > 5:
            results.append({
                "title": title,
                "url": url,
                "engine": "baidu"
            })
    return results


def extract_360(snapshot: str) -> list:
    """提取360搜索结果"""
    results = []
    pattern = r'heading "([^"]+)" \[level=3\]:.*?/url: (https?://[^\s\\]+so\.com[^\s\\]+|/[^\s\\]+)'
    matches = re.findall(pattern, snapshot, re.DOTALL)
    for title, url in matches:
        title = title.strip()
        if len(title) > 5:
            if url.startswith('/'):
                url = f"https://www.so.com{url}"
            results.append({
                "title": title,
                "url": url,
                "engine": "360"
            })
    return results


EXTRACTORS = {
    "sogou": extract_sogou,
    "baidu": extract_baidu,
    "360": extract_360,
}


def search_engine(engine_id: str, query: str) -> list:
    """搜索单个引擎，返回结果列表"""
    engine_cfg = next(e for e in ENGINES if e["id"] == engine_id)
    q_encoded = quote(query)

    try:
        tab_id = create_tab(engine_cfg["url_template"].format(q=q_encoded))
        time.sleep(5)  # 等待 JS 动态内容加载

        snapshot = get_snapshot(tab_id)
        extractor = EXTRACTORS[engine_id]
        results = extractor(snapshot)

        # 去重
        seen = set()
        deduped = []
        for r in results:
            if r["title"] not in seen:
                seen.add(r["title"])
                deduped.append(r)

        return deduped

    except Exception as e:
        print(f"  [{engine_cfg['name']}] 出错: {e}")
        return []


def multi_engine_search(query: str, engines: list = None) -> list:
    """多引擎搜索，按权重合并结果"""
    if engines is None:
        engines = [e["id"] for e in ENGINES]

    all_results = []
    for engine_id in engines:
        if engine_id not in EXTRACTORS:
            continue
        results = search_engine(engine_id, query)
        if results:
            cfg = next(e for e in ENGINES if e["id"] == engine_id)
            weight = cfg["weight"]
            for r in results:
                r["weight"] = weight
            all_results.extend(results)
            print(f"  [{cfg['name']}] 获取 {len(results)} 条")

    # 按权重排序
    all_results.sort(key=lambda x: x["weight"], reverse=True)
    return all_results


def check_health() -> bool:
    """检查 Camoufox 服务状态"""
    r = subprocess.run(["curl", "-s", f"{CAMOUFOX_URL}/health"],
                       capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
        return data.get("ok", False)
    except:
        return False


def main():
    parser = argparse.ArgumentParser(description="Star Search v8 - 搜狗优先 多引擎搜索")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--engine", choices=[e["id"] for e in ENGINES], default=None,
                        help="指定引擎（默认多引擎）")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--list", action="store_true", help="列出可用引擎")
    args = parser.parse_args()

    if args.list:
        print("可用引擎:")
        for e in ENGINES:
            print(f"  {e['id']:8} - {e['name']} (权重:{e['weight']})")
        return

    # 检查服务
    if not check_health():
        print("❌ Camoufox 服务未运行，请先启动: camoufox --port 9377")
        sys.exit(1)

    engines = [args.engine] if args.engine else [e["id"] for e in ENGINES]
    engine_names = "/".join(next(e["name"] for e in ENGINES if e["id"] == eid) for eid in engines)

    print(f"\n🔍 Star Search v8 - 搜索: {args.query}")
    print(f"引擎: {engine_names}")

    results = multi_engine_search(args.query, engines)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"📊 共获取 {len(results)} 条结果")
        print(f"{'='*60}")
        for i, r in enumerate(results[:10], 1):
            tag = f"[{r['engine']}]"
            print(f"{i}. {r['title'][:65]}")
            print(f"   {tag} {r['url'][:65]}")
            print()


if __name__ == "__main__":
    main()
