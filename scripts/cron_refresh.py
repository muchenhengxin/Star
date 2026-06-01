#!/usr/bin/env python3
"""
star-search 定时增量客户端 v15.0

调用 api_server 的 /v1/search/refresh 接口，
对每个监控的 query 定期拉新（默认 30 分钟），
输出 JSON 行到 stdout 供 subagent / 管道消费。

用法:
  # 单次拉
  python3 scripts/cron_refresh.py --query "华为鸿蒙 PC" --mode dev

  # 多 query 批量
  python3 scripts/cron_refresh.py --queries "华为鸿蒙" "DeepSeek V4" "英伟达"

  # 配合 watch 自动循环
  python3 scripts/cron_refresh.py --queries "..." --loop 1800
"""
import argparse, json, sys, time, asyncio
import httpx

DEFAULT_API = "http://127.0.0.1:9800"

async def refresh(client, api, query, mode='dev', top=10):
    try:
        r = await client.post(f"{api}/v1/search/refresh",
            json={"query": query, "mode": mode, "top": top}, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "query": query}

async def main(args):
    api = args.api.rstrip('/')
    queries = args.queries or ([args.query] if args.query else [])
    if not queries:
        print("需要 --query 或 --queries", file=sys.stderr); sys.exit(1)

    async with httpx.AsyncClient() as client:
        while True:
            ts = int(time.time())
            results = await asyncio.gather(*[
                refresh(client, api, q, mode=args.mode, top=args.top) for q in queries
            ])
            # 输出 JSONL（每行一个 query 的结果）
            for r in results:
                r['_ts'] = ts
                print(json.dumps(r, ensure_ascii=False))
            sys.stdout.flush()

            if not args.loop:
                break
            time.sleep(args.loop)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=DEFAULT_API)
    p.add_argument("--query", help="单 query")
    p.add_argument("--queries", nargs="+", help="多 query 批量")
    p.add_argument("--mode", default="dev", choices=["dev", "news", "deep", "policy", "stock", "quick"])
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--loop", type=int, default=0, help="秒，0=单次；N=每N秒循环")
    args = p.parse_args()
    asyncio.run(main(args))
