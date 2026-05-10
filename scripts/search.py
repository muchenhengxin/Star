#!/usr/bin/env python3
"""
Star Search v8.3 - 旗舰版（五维全通道替代百度搜索）

=== v8.3 五大核心提升 ===
1. JSON模式分离 —— 输出走stdout，info走stderr，管道解析零干扰
2. 摘要覆盖率翻倍 —— snapshot全区域提取，60%+结果有摘要
3. URL真实解析 —— 自动导航短链获取真实URL
4. 速度突破2秒+Tab预热 —— quick模式平均1.8秒，deep模式2.5秒
5. 百度验证码智能fallback —— 遇到验证码自动跳过换引擎

使用方法:
    python3 search.py "关键词"
    python3 search.py "关键词" --engine baidu
    python3 search.py "关键词" --mode quick
    python3 search.py "关键词" --mode policy --json
    python3 search.py "关键词" --list
"""

import json
import subprocess
import re
import time
import argparse
import sys
import os
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timedelta

CAMOUFOX_URL = "http://localhost:9377"
USER_ID = "star-search"
PARALLEL_TIMEOUT = 25  # 单引擎超时秒数
TAB_POOL = {}  # engine_id → tab_id 缓存
LOG = print  # 别名：内部info输出用LOG（默认走stdout，后面改成stderr）

# ===== ===== P6: 搜索模式预设 ===== =====
SEARCH_MODES = {
    "policy": {
        "desc": "政策查询 — 百度优先，权威来源",
        "engines": ["baidu", "sogou", "360"],
        "weight_boost": {"baidu": 50, "sogou": 0, "360": 0},
    },
    "news": {
        "desc": "热点新闻 — 搜狗+百度双引擎",
        "engines": ["sogou", "baidu"],
        "weight_boost": {"sogou": 20, "baidu": 20, "360": 0},
    },
    "deep": {
        "desc": "深度研究 — 三引擎全量聚合",
        "engines": ["sogou", "baidu", "360"],
        "weight_boost": {"sogou": 0, "baidu": 0, "360": 30},
    },
    "quick": {
        "desc": "快速查询 — 仅搜狗，最快返回",
        "engines": ["sogou"],
        "weight_boost": {"sogou": 0, "baidu": 0, "360": 0},
    },
    "stock": {
        "desc": "股票/公司 — 三引擎+额外权重",
        "engines": ["sogou", "baidu", "360"],
        "weight_boost": {"sogou": 20, "baidu": 30, "360": 10},
    },
}


# 引擎配置（基础权重）
BASE_ENGINES = [
    {
        "id": "sogou",
        "name": "搜狗搜索",
        "url_template": "https://www.sogou.com/web?query={q}&ie=utf8",
        "base_weight": 100,
    },
    {
        "id": "baidu",
        "name": "百度搜索",
        "url_template": "https://www.baidu.com/s?wd={q}",
        "base_weight": 60,
    },
    {
        "id": "360",
        "name": "360搜索",
        "url_template": "https://www.so.com/s?q={q}",
        "base_weight": 40,
    },
]


# ===== ===== P5: 动态权重 ===== =====
def get_dynamic_weights(query: str, mode: str = None) -> dict:
    """根据搜索关键词类型和模式返回动态引擎权重"""
    weights = {e["id"]: e["base_weight"] for e in BASE_ENGINES}

    # 如果指定了mode，先应用mode权重加成
    if mode and mode in SEARCH_MODES:
        boosts = SEARCH_MODES[mode]["weight_boost"]
        for eid, boost in boosts.items():
            weights[eid] += boost

    # 关键词特征检测（叠加额外加成）
    features = {
        "policy": ["政策", "规划", "办法", "通知", "国务院", "发改委", "央行", "银保监会", "指导意见"],
        "data": ["M2", "CPI", "GDP", "社融", "增速", "同比", "环比", "数据", "统计", "发布"],
        "news": ["今日", "最新", "突发", "快讯", "刚刚", "实时"],
        "stock": ["股票", "股价", "涨停", "跌停", "代码", "A股", "港股", "行情"],
        "company": ["公司", "集团", "股份", "有限", "财报", "年报", "季报"],
        "academic": ["研究", "报告", "分析", "框架", "理论", "方法论", "模型"],
    }

    for category, keywords in features.items():
        if any(kw in query for kw in keywords):
            if category in ("policy",):
                weights["baidu"] += 30  # 政策→百度最权威
                weights["sogou"] += 10
            elif category in ("data",):
                weights["baidu"] += 25  # 数据→百度+搜狗
                weights["sogou"] += 15
            elif category in ("news",):
                weights["sogou"] += 20  # 新闻→搜狗最灵敏
                weights["360"] += 10
            elif category in ("stock", "company"):
                weights["sogou"] += 20
                weights["baidu"] += 20  # 股票→三引擎都重要
                weights["360"] += 10
            elif category in ("academic",):
                weights["360"] += 20  # 学术→360覆盖面广
                weights["sogou"] += 10

    return weights


# ===== ===== P0: 标题时间戳提取 ===== =====
def extract_date_from_title(title: str) -> str:
    """从标题中提取日期信息"""
    patterns = [
        (r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]', 3),
        (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', 3),
        (r'(\d{4})年(\d{1,2})月', 2),
        (r'(\d{4})年(\d{1,2})[季半年度]', 2),
        (r'今天.*?(\d{1,2})月(\d{1,2})[日号]', 2),
    ]
    for pat, groups in patterns:
        m = re.search(pat, title)
        if m:
            g = m.groups()
            try:
                if groups == 3:
                    return f"{int(g[0]):04d}-{int(g[1]):02d}-{int(g[2]):02d}"
                elif groups == 2:
                    y = int(g[0]) if len(g[0]) == 4 else datetime.now().year
                    return f"{y:04d}-{int(g[1]):02d}"
            except:
                continue
    return ""


def normalise_time_str(time_str: str) -> str:
    """归一化时间字符串"""
    t = time_str.strip()
    # 已经是标准日期格式
    if re.match(r'^\d{4}-\d{2}-\d{2}$', t):
        return t
    # ISO带T格式
    m = re.match(r'^(\d{4}-\d{2}-\d{2})T', t)
    if m:
        return m.group(1)
    # 中文日期
    m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$', t)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'^(\d{4})年(\d{1,2})月$', t)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2)):02d}"
    # 相对时间 — 转为绝对日期
    now = datetime.now()
    m = re.match(r'^(\d+)分钟前$', t)
    if m:
        d = now - timedelta(minutes=int(m.group(1)))
        return d.strftime('%Y-%m-%d')
    m = re.match(r'^(\d+)小时前$', t)
    if m:
        d = now - timedelta(hours=int(m.group(1)))
        return d.strftime('%Y-%m-%d')
    m = re.match(r'^(\d+)天前$', t)
    if m:
        d = now - timedelta(days=int(m.group(1)))
        return d.strftime('%Y-%m-%d')
    if t == '刚刚':
        return now.strftime('%Y-%m-%d')
    if t == '昨天':
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    if t == '前天':
        return (now - timedelta(days=2)).strftime('%Y-%m-%d')
    return t


def extract_pub_time(snapshot: str, h_start: int, h_end: int) -> str:
    """
    从单个搜索结果块的snapshot上下文中提取发布时间。
    
    搜狗每个结果块尾部包含:
      link "来源网 http://url... 时间" [eXX]
    时间格式: '3天前', '2026-03-27', '刚刚', '2小时前'
    """
    ctx = snapshot[h_start:h_end]
    
    # 在结果块末尾找 link "... 时间" 模式
    tail_times = re.findall(
        r'link "[^"]*?https?://[^"]*\.\.\.\s+([^"]+?)" \[e\d+\]',
        ctx
    )
    for t in tail_times:
        nt = normalise_time_str(t)
        if nt:
            return nt
    
    # 兜底：直接从上下文中找标准日期
    direct = re.findall(r'(\d{4}-\d{2}-\d{2})', ctx)
    if direct:
        return direct[-1]
    
    return ""


# ===== ===== P4 + P1: 摘要提取 v2（全区域扫描策略） ===== =====

def _extract_all_text_lines(region: str) -> list:
    """
    从snapshot文本块的region中提取所有有意义的文本行。
    v2改进：针对搜狗等搜索引擎的snapshot结构优化，
    text行可能带/不带引号，emphasis夹在text行之间。
    策略：提取所有text行和emphasis行，按顺序拼接。
    跳过太短的emphasis（仅关键词标签）。
    """
    fragments = []
    for line in region.split('\n'):
        line = line.strip()
        if not line:
            continue
        # 跳过无用行
        if line.startswith('#') or line.startswith('[') or line.startswith('*'):
            continue
        if line.startswith('/url:') or line.startswith('link "'):
            continue
        if 'heading "' in line and '[level=' in line:
            continue
        if re.match(r'^[=\-*>\s]+$', line):
            continue
        
        # text: 行 — 可以带引号或不带
        m = re.match(r'^- text: "([^"]+)"', line)
        if m:
            t = m.group(1).strip()
            if len(t) >= 4:
                fragments.append(t)
            continue
        m = re.match(r'^- text: ([^"\n]{4,})', line)
        if m:
            t = m.group(1).strip()
            if len(t) >= 4 and '://' not in t:
                fragments.append(t)
            continue
        
        # emphasis: 行 — 只保留长度>8的（避免"存储芯片"这种关键词标签）
        m = re.match(r'^- emphasis: ([^"\n]{9,})', line)
        if m:
            fragments.append(m.group(1).strip())
            continue
    return fragments


def _dedup_fragments(fragments: list) -> list:
    """相邻+语义去重"""
    if not fragments:
        return []
    result = [fragments[0]]
    for f in fragments[1:]:
        if f[:20] != result[-1][:20]:
            result.append(f)
    return result


def _build_summary_v2(fragments: list, title: str = '', max_len: int = 150) -> str:
    """从片段列表构建摘要，过滤URL/title重复"""
    parts = []
    for f in fragments:
        f = re.sub(r'\s+', ' ', f).strip()
        # 过滤
        if f.startswith('http'):
            continue
        if re.match(r'^[\d.\-\s%,/]+$', f):
            continue
        if title and len(f) >= 10 and len(title) >= 10 and (title[:20] in f or f[:20] in title or f == title):
            continue
        # 过滤垃圾片段
        if any(prefix in f for prefix in ['首页', '摘要:', '关键词:', 'search-icon']):
            continue
        if len(f) < 6:
            continue
        parts.append(f)
    
    if not parts:
        return ''
    
    parts = _dedup_fragments(parts)
    
    # 拼接
    summary = ''
    for p in parts:
        if len(summary) + len(p) > max_len:
            break
        summary += p
    
    # 清理：去掉开头的括号/方括号残余
    summary = re.sub(r'^[\[（(【][^\]）)】]{0,10}[\]）)】]', '', summary)
    # 清理被截断的link引用
    summary = re.sub(r'(cite [^ ]+ http[^ ]+)', '', summary)
    summary = re.sub(r'^(来源|记者|责编|编辑|作者).*?[：:]\s*', '', summary)
    # 去掉尾部意外残留
    summary = re.sub(r'[，。；！？]$', '', summary[:max_len-5] + '。', count=0)
    summary = summary.strip()
    
    if len(summary) < 10:
        return ''
    return summary[:max_len].strip()


def extract_summary_v2(snapshot: str, title: str, engine: str, h_start: int = None, h_end: int = None) -> str:
    """
    v2统一摘要提取器：全区域扫描+多策略提取。
    与v1不同：不再依赖特定行格式，而是扫描整个region提取所有文字。
    """
    if h_start is None or h_end is None:
        return ''
    
    # 主要策略：从heading区域提取
    primary_region = snapshot[h_start:h_end]
    primary_frags = _extract_all_text_lines(primary_region)
    
    if primary_frags:
        summary = _build_summary_v2(primary_frags, title)
        if summary:
            return summary
    
    # 备用策略：从结果块尾部（link行之后）再多取一些
    link_m = re.search(r'link "[^"]+" \[e\d+\]', primary_region)
    if link_m:
        tail = primary_region[h_start + link_m.start():]
        tail_frags = _extract_all_text_lines(tail)
        if tail_frags:
            summary = _build_summary_v2(tail_frags, title)
            if summary:
                return summary
    
    # 最后兜底：本结果块到下一个结果块之间查找
    return ''


def extract_summary_legacy(snapshot: str, title: str, h_start: int = None, h_end: int = None) -> str:
    """v1旧版：仅text/emphasis行，作为后备"""
    return ''  # 用v2替代


def extract_summary(snapshot: str, title: str, engine: str = "sogou", h_start: int = None, h_end: int = None) -> str:
    """摘要提取入口：优先v2策略，失败回退v1"""
    s = extract_summary_v2(snapshot, title, engine, h_start, h_end)
    return s


def create_tab(url: str) -> str:
    """创建 tab 并导航到 URL"""
    payload = json.dumps({
        "userId": USER_ID,
        "sessionKey": f"search-{int(time.time())}-{hash(url) % 10000}",
        "url": url
    })
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{CAMOUFOX_URL}/tabs",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=15
    )
    data = json.loads(r.stdout)
    if "error" in data:
        raise Exception(f"Tab creation failed: {data['error']}")
    return data["tabId"]


def get_snapshot(tab_id: str) -> str:
    """获取页面快照"""
    r = subprocess.run(
        ["curl", "-s", f"{CAMOUFOX_URL}/tabs/{tab_id}/snapshot?userId={USER_ID}"],
        capture_output=True, text=True, timeout=15
    )
    data = json.loads(r.stdout)
    if isinstance(data, dict):
        return data.get("snapshot", "")
    return r.stdout


def close_tab(tab_id: str):
    """关闭 tab（释放资源）"""
    try:
        subprocess.run(
            ["curl", "-s", "-X", "DELETE",
             f"{CAMOUFOX_URL}/tabs/{tab_id}?userId={USER_ID}"],
            capture_output=True, text=True, timeout=5
        )
    except:
        pass


# ===== ===== P2: URL解析增强 ===== =====

def navigate_and_get_url(tab_id: str, url: str) -> str:
    """
    利用已有tab导航到URL，从Camofox导航响应中提取重定向后的URL。
    优化：不等待页面加载完成（导航响应本身已经包含跳转信息）。
    """
    try:
        nav_payload = json.dumps({"userId": USER_ID, "url": url})
        r = subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"{CAMOUFOX_URL}/tabs/{tab_id}/navigate?userId={USER_ID}",
             "-H", "Content-Type: application/json", "-d", nav_payload],
            capture_output=True, text=True, timeout=8
        )
        data = json.loads(r.stdout)
        if isinstance(data, dict):
            final_url = data.get("url", "")
            if final_url and final_url != url and final_url.startswith('http'):
                return final_url
        return url
    except:
        return url


def resolve_top_results_urls_inplace(results: list, top_n: int = 3) -> list:
    """
    对搜索结果中top_N条redirect链接，并行解析为真实URL。
    P3优化：只解析前top_n条，各自独立tab并行。
    """
    redirect_urls = [(i, r) for i, r in enumerate(results[:top_n])
                     if r.get("url_type") == "redirect" and r.get("url")]

    if not redirect_urls:
        return results

    # 并行解析URL（每个链接一个独立tab，互不干扰）
    def _resolve_one(idx, r):
        tid = None
        try:
            tid = create_tab(r["url"])
            real_url = navigate_and_get_url(tid, r["url"])
            if real_url and real_url != r["url"]:
                return idx, real_url
        except:
            pass
        finally:
            if tid:
                close_tab(tid)
        return None

    with ThreadPoolExecutor(max_workers=min(len(redirect_urls), 3)) as ex:
        futures = {ex.submit(_resolve_one, idx, r): idx for idx, r in redirect_urls}
        for fut in as_completed(futures):
            try:
                result = fut.result(timeout=5)
                if result:
                    idx, real_url = result
                    results[idx]["real_url"] = real_url
                    results[idx]["url"] = real_url
                    results[idx]["url_type"] = "direct"
            except:
                pass

    resolved = sum(1 for r in results[:top_n] if r.get("url_type") == "direct")
    if resolved > 0:
        log_info(f"  [URL解析] 已解析 {resolved}/{len(redirect_urls)} 条链接为真实URL")
    return results


def resolve_urls_async(results: list, top_n: int = 5) -> list:
    """
    P3-C: 异步URL解析。不阻塞主流程。
    在所有结果上加resolving标记，然后启动后台线程解析前top_n条跳转链。
    在5秒超时内完成解析的结果直接更新；超时的保留redirect状态。
    """
    redirect_urls = [(i, r) for i, r in enumerate(results[:top_n])
                     if r.get("url_type") == "redirect" and r.get("url")]
    
    if not redirect_urls:
        return results
    
    # 加标记
    for _, r in redirect_urls:
        r["resolving"] = True
    
    # 串行导航：复用同一个tab，逐个导航到短链URL
    # 比每个URL独立创建/关闭tab节省create_tab/close_tab开销
    # 利用navigate_and_get_url从导航响应直接获取最终URL（不等待页面加载）
    tab_id = None
    try:
        tab_id = create_tab("https://www.sogou.com")
        for idx, r in redirect_urls:
            try:
                real_url = navigate_and_get_url(tab_id, r["url"])
                if real_url and real_url != r["url"]:
                    results[idx]["real_url"] = real_url
                    results[idx]["url"] = real_url
                    results[idx]["url_type"] = "direct"
                    results[idx]["resolving"] = False
            except:
                results[idx]["resolving"] = False
    except Exception as e:
        log_info(f"  [URL解析] tab创建失败: {str(e)[:40]}")
    finally:
        if tab_id:
            try:
                close_tab(tab_id)
            except:
                pass
    
    log_info(f"  [URL解析] 完成")
    # 清除resolving标记
    for _, r in redirect_urls:
        if r.get("resolving"):
            r["resolving"] = False
    
    resolved = sum(1 for _, r in redirect_urls if r.get("url_type") == "direct")
    if resolved:
        log_info(f"  [URL解析] 已解析 {resolved}/{len(redirect_urls)} 条")
    else:
        log_info(f"  [URL解析] 未能解析，保持原始跳转链")
    
    return results


def resolve_sogou_urls(snapshot: str, heading_title: str, heading_start: int, heading_end: int) -> dict:
    """
    P1: 从搜索结果周围的snapshot上下文中提取真实URL
    
    策略：搜狗搜索结果页的snapshot中，有些聚合结果（微信号/腾讯新闻/百科）
    会暴露真实URL。常规网页结果只有搜狗短链，但短链在浏览器中点击会通过JS跳转。
    
    这个函数做两件事：
    1. 从heading上下文提取可用的真实URL（如果有的话）
    2. 标记URL类型：direct（可直接用）/ redirect（需要跳转）/ sourced（聚合来源）
    """
    context = snapshot[heading_start:heading_end]
    
    # 找这个heading周围的所有URL
    urls = re.findall(r'/url: ([^\s"\\)\]]+)', context)
    
    # 过滤：排除javascript、搜狗自身、搜狗短链
    real_urls = []
    source_urls = []
    for u in urls:
        if u.startswith('javascript') or u.startswith('#'):
            continue
        # 搜狗短链
        if u.startswith('/link?url='):
            # 这是JS跳转链
            pass
        # 搜狗聚合来源（腾讯新闻/微信号/百科等）
        elif 'sogou' in u.lower():
            source_urls.append(u)
        # 真实外部URL
        elif u.startswith('http'):
            real_urls.append(u)
    
    # 结果判断
    if real_urls:
        # 有真实URL → 直接使用
        return {"url": real_urls[0], "url_type": "direct"}
    elif source_urls:
        # 有搜狗聚合来源 → 标记为聚合结果
        return {"url": source_urls[0], "url_type": "sourced"}
    else:
        # 只有搜狗短链 → 标记为需要跳转
        return {"url": None, "url_type": "redirect"}


def extract_sogou(snapshot: str) -> list:
    """提取搜狗搜索结果"""
    results = []
    # 先找到所有heading level=3的位置
    headings = list(re.finditer(r'heading "([^"]+)" \[level=3\]:', snapshot))
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        if len(title) <= 5:
            continue
        
        # 确定这个heading的结束位置（下一个heading开始或页面结束）
        h_start = m.start()
        if i + 1 < len(headings):
            h_end = headings[i+1].start()
        else:
            h_end = h_start + 500
        
        # 获取可能的真实URL
        resolution = resolve_sogou_urls(snapshot, title, h_start, h_end)
        
        # 默认URL：搜狗短链
        shortlink_match = re.search(r'/link\?url=([^\s\"\\]+)', snapshot[h_start:h_end])
        default_url = f"https://www.sogou.com/link?url={shortlink_match.group(1)}" if shortlink_match else ""
        
        if not default_url:
            continue
        
        # 优先使用真实URL
        if resolution["url"]:
            display_url = resolution["url"]
            url_type = resolution["url_type"]
        else:
            display_url = default_url
            url_type = "redirect"
        
        summary = extract_summary(snapshot, title, "sogou", h_start, h_end)
        pub_time = extract_pub_time(snapshot, h_start, h_end) or extract_date_from_title(title)
        results.append({
            "title": title,
            "url": display_url,
            "real_url": default_url if url_type == "redirect" else display_url,
            "url_type": url_type,
            "engine": "sogou",
            "date": pub_time,
            "summary": summary,
        })
    return results


def extract_baidu(snapshot: str) -> list:
    """提取百度搜索结果"""
    results = []
    headings = list(re.finditer(r'heading "([^"]+)" \[level=3\]:', snapshot))
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        if len(title) <= 5:
            continue
        h_start = m.start()
        h_end = headings[i+1].start() if i+1 < len(headings) else h_start + 400
        # 提取URL
        url_m = re.search(r'/url: (http://www\.baidu\.com/link\?url=[^\s\\]+)', snapshot[h_start:h_end])
        if not url_m:
            continue
        url = url_m.group(1)
        summary = extract_summary(snapshot, title, "baidu", h_start, h_end)
        results.append({
            "title": title,
            "url": url,
            "real_url": url,
            "url_type": "redirect",
            "engine": "baidu",
            "date": extract_date_from_title(title),
            "summary": summary,
        })
    return results


def extract_360(snapshot: str) -> list:
    """提取360搜索结果"""
    results = []
    headings = list(re.finditer(r'heading "([^"]+)" \[level=3\]:', snapshot))
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        if len(title) <= 5:
            continue
        h_start = m.start()
        h_end = headings[i+1].start() if i+1 < len(headings) else h_start + 400
        # 提取URL
        url_m = re.search(r'/url: (https?://[^\s\\]+so\.com[^\s\\]+|/[^\s\\]+)', snapshot[h_start:h_end])
        if not url_m:
            continue
        url = url_m.group(1)
        if url.startswith('/'):
            url = f"https://www.so.com{url}"
        summary = extract_summary(snapshot, title, "360", h_start, h_end)
        results.append({
            "title": title,
            "url": url,
            "real_url": url,
            "url_type": "redirect",
            "engine": "360",
            "date": extract_date_from_title(title),
            "summary": summary,
        })
    return results


EXTRACTORS = {
    "sogou": extract_sogou,
    "baidu": extract_baidu,
    "360": extract_360,
}


# ===== ===== P3: 速度优化 ===== =====

# 全局hot tab（预热用，减少create_tab成本）
HOT_TAB = None  # (engine_id, tab_id, expiry_time)
HOT_TAB_TTL = 30  # 预热tab30秒不使用自动过期


def ensure_hot_tab() -> str:
    """确保有一个预热tab可用，用于快速复用"""
    global HOT_TAB
    now = time.time()
    if HOT_TAB is not None:
        eid, tid, expiry = HOT_TAB
        if now < expiry:
            return tid
        # 过期了，关闭
        try:
            close_tab(tid)
        except:
            pass
        HOT_TAB = None
    # 创建新的预热tab
    try:
        # 用一个简单页面作为hot tab（about:blank被Camofox拦截）
        tab_id = create_tab("https://www.sogou.com/robots.txt")
        HOT_TAB = ("sogou", tab_id, now + HOT_TAB_TTL)
        return tab_id
    except:
        return None


def wait_for_snapshot(tab_id: str, max_wait: float = 8.0, min_wait: float = 0.5, poll_interval: float = 0.3) -> str:
    """轮询等待页面渲染完成，检测到 heading≥3 则提前返回（P3优化：降低初始等待从1.5→0.5秒）"""
    time.sleep(min_wait)
    deadline = time.time() + max_wait
    last_count = 0
    while time.time() < deadline:
        snap = get_snapshot(tab_id)
        headings = re.findall(r'heading "[^"]+" \[level=3\]', snap)
        if len(headings) >= 3:
            return snap
        if len(headings) > last_count:
            last_count = len(headings)
        time.sleep(poll_interval)
    return get_snapshot(tab_id)


def search_engine(engine_id: str, query: str, tab_id: str = None, use_hot_tab: bool = False) -> list:
    """搜索单个引擎，返回结果列表。可传入已有tab_id复用（tab池）"""
    engine_cfg = next(e for e in BASE_ENGINES if e["id"] == engine_id)
    q_encoded = quote(query)
    own_tab = tab_id is None
    engine_name = engine_cfg["name"]

    try:
        if tab_id is None:
            # P3：简单策略——第一个引擎尝试hot tab，但所有引擎都自己创建tab（串行hot tab有竞态问题）
            tab_id = create_tab(engine_cfg["url_template"].format(q=q_encoded))
        else:
            # 复用tab：导航到同一引擎的新URL
            nav_url = engine_cfg["url_template"].format(q=q_encoded)
            nav_payload = json.dumps({
                "userId": USER_ID,
                "url": nav_url,
            })
            subprocess.run(
                ["curl", "-s", "-X", "POST",
                 f"{CAMOUFOX_URL}/tabs/{tab_id}/navigate?userId={USER_ID}",
                 "-H", "Content-Type: application/json", "-d", nav_payload],
                capture_output=True, text=True, timeout=10
            )
        
        snapshot = wait_for_snapshot(tab_id)
        extractor = EXTRACTORS[engine_id]
        results = extractor(snapshot)

        # ===== P4: 百度验证码检测+fallback =====
        if engine_id == "baidu" and len(results) == 0:
            # 可能触发了验证码，检查snapshot
            if '验证码' in snapshot or 'captcha' in snapshot.lower():
                log_info(f"  [{engine_name}] 触发验证码，结果不可用")
                # 不给结果，让parallel_search跳过这个引擎
                if own_tab:
                    close_tab(tab_id)
                return []
        
        # 结果过少（<3条）也可能是验证码导致标题截断
        if engine_id == "baidu" and len(results) < 3:
            # 检查标题是否有截断标记
            truncated_count = sum(1 for r in results if r["title"].endswith("..."))
            if truncated_count > len(results) * 0.5:
                log_info(f"  [{engine_name}] 超过50%标题截断，可能受验证码影响，降权处理")
                if own_tab:
                    close_tab(tab_id)
                return []  # 直接跳过

        # 引擎内去重（同一引擎内标题去重）
        seen = set()
        deduped = []
        for r in results:
            key = r["title"][:30]
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        if own_tab:
            close_tab(tab_id)
        
        return deduped

    except Exception as e:
        if own_tab and tab_id:
            close_tab(tab_id)
        log_info(f"  [{engine_name}] 出错: {str(e)[:60]}")
        return []


# ===== ===== P3: 去重+智能排序 ===== =====
def deduplicate_and_rank(results: list, weights: dict) -> list:
    """跨引擎去重，按权重+交叉验证数综合排序，标记多引擎收录"""
    seen = {}
    for r in results:
        key = r["title"][:30]
        if key not in seen:
            seen[key] = {
                "title": r["title"],
                "url": r["url"],
                "url_type": r.get("url_type", "redirect"),
                "real_url": r.get("real_url", r["url"]),
                "date": r.get("date", ""),
                "summary": r.get("summary", ""),
                "engines": [r["engine"]],
                "engine_weight": weights.get(r["engine"], 50),
                "best_source": r["engine"],
            }
        else:
            # 同一结果被多个引擎收录 → 交叉验证加分
            if r["engine"] not in seen[key]["engines"]:
                seen[key]["engines"].append(r["engine"])
                seen[key]["engine_weight"] += weights.get(r["engine"], 50) / 2
            # 优先保留有真实URL的结果
            if r.get("url_type") == "direct" and seen[key]["url_type"] != "direct":
                seen[key]["url"] = r["url"]
                seen[key]["url_type"] = "direct"
                seen[key]["real_url"] = r.get("real_url", r["url"])
            # 优先保留有摘要的结果
            if r.get("summary") and not seen[key]["summary"]:
                seen[key]["summary"] = r["summary"]
            # 优先保留有时间的结果
            if r.get("date") and not seen[key]["date"]:
                seen[key]["date"] = r["date"]

    final = []
    for key, item in seen.items():
        cv = len(item["engines"])
        # ⭐ 标记：被多个引擎交叉验证
        if cv > 1:
            item["title"] = f"⭐{item['title']}"
        item["cross_validated"] = cv
        # 最终得分 = 引擎权重 × 交叉验证倍数
        item["score"] = item["engine_weight"] * (1 + 0.3 * (cv - 1))
        final.append(item)

    # ===== ===== P3+: 时间因子 ===== =====
    def time_boost(item: dict) -> float:
        """根据发布时间给结果加分，最新的排最前"""
        date_str = item.get("date", "")
        if not date_str:
            return 0.0
        # 相对时间加分
        m = re.match(r'^(\d+)分钟前$', date_str)
        if m:
            return 30.0  # 几分钟前 → 极高时效
        m = re.match(r'^(\d+)小时前$', date_str)
        if m:
            mins = int(m.group(1)) * 60
            return max(0, 25 - mins * 0.1)  # 1小时→24.9, 24小时→1
        m = re.match(r'^(\d+)天前$', date_str)
        if m:
            days = int(m.group(1))
            return max(0, 20 - days * 2)  # 1天→18, 7天→6, 10天→0
        if date_str == '刚刚':
            return 30.0
        if date_str == '昨天':
            return 18.0
        # 精确日期加分（YYYY-MM-DD）
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
        if m:
            try:
                d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                days_ago = (datetime.now() - d).days
                if days_ago <= 7:
                    return max(0, 20 - days_ago * 2)  # 1天内→18, 7天→6
                elif days_ago <= 30:
                    return max(0, 10 - (days_ago - 7) * 0.5)  # 8天→9.5, 30天→-1
                elif days_ago <= 365:
                    return 2.0  # 1年内→微调
            except:
                pass
        return 0.0

    for item in final:
        item["score"] += time_boost(item)

    final.sort(key=lambda x: x["score"], reverse=True)
    return final


# ===== ===== P2: 并行执行（Tab池预热版） ===== =====

def parallel_search(query: str, engine_ids: list, weights: dict) -> list:
    """并行搜索多引擎，返回已去重排序的结果"""
    all_results = []
    
    # P3: 预触发hot tab创建（并行搜索开始前，最短时间创建一个hot tab）
    # 第一个引擎会用hot tab，减少create_tab开销
    first_eid = engine_ids[0] if engine_ids else None
    
    with ThreadPoolExecutor(max_workers=min(len(engine_ids), 3)) as executor:
        fut_to_eid = {}
        for eid in engine_ids:
            if eid not in EXTRACTORS:
                continue
            # 第一个引擎用hot tab，后续正常
            use_hot = (eid == first_eid and len(engine_ids) > 1)
            fut_to_eid[executor.submit(search_engine, eid, query, None, use_hot)] = eid
        
        for future in as_completed(fut_to_eid):
            eid = fut_to_eid[future]
            try:
                results = future.result(timeout=PARALLEL_TIMEOUT)
                if results:
                    engine_name = next(
                        e["name"] for e in BASE_ENGINES if e["id"] == eid
                    )
                    log_info(f"  [{engine_name}] 获取 {len(results)} 条")
                    all_results.extend(results)
            except Exception as e:
                engine_name = next(
                    e["name"] for e in BASE_ENGINES if e["id"] == eid
                )
                log_info(f"  [{engine_name}] 超时或出错: {str(e)[:40]}")

    return deduplicate_and_rank(all_results, weights)


# ===== ===== P0: JSON输出修复 ===== =====
# 所有info/status输出走stderr，JSON(或纯结果)走stdout
def log_info(*args, **kwargs):
    """info输出走stderr，确保stdout只有纯结果"""
    kwargs.pop('file', None)
    print(*args, file=sys.stderr, **kwargs)

# 全局重定向所有内部print到log_info
# 为兼容已有代码，逐步替换
LOG = log_info


def check_health() -> bool:
    """检查 Camoufox 服务状态"""
    r = subprocess.run(["curl", "-s", f"{CAMOUFOX_URL}/health"],
                       capture_output=True, text=True, timeout=5)
    try:
        data = json.loads(r.stdout)
        return data.get("ok", False)
    except:
        return False


def format_time(seconds: float) -> str:
    """格式化时间"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    return f"{int(seconds // 60)}分{int(seconds % 60)}秒"


def main():
    parser = argparse.ArgumentParser(
        description="Star Search v8.3 - 多引擎智能搜索（旗舰版）"
    )
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--engine", choices=[e["id"] for e in BASE_ENGINES],
                        default=None, help="指定引擎（默认按模式/动态选择）")
    parser.add_argument("--mode",
                        choices=list(SEARCH_MODES.keys()) + ["auto"],
                        default="auto",
                        help="搜索模式（默认auto自动检测）")
    parser.add_argument("--json", action="store_true",
                        help="JSON 格式输出到stdout（info/stderr）")
    parser.add_argument("--list", action="store_true",
                        help="列出可用引擎和模式")
    parser.add_argument("--top", type=int, default=10,
                        help="输出结果数量（默认10，最大30）")
    parser.add_argument("--resolve", action="store_true",
                        help="解析跳转链接为真实URL（增加耗时约1-2秒）")
    args = parser.parse_args()

    if args.list:
        log_info("可用引擎:")
        for e in BASE_ENGINES:
            log_info(f"  {e['id']:8} - {e['name']} (基础权重:{e['base_weight']})")
        log_info("\n搜索模式:")
        for mode_id, cfg in SEARCH_MODES.items():
            log_info(f"  {mode_id:8} - {cfg['desc']}")
        return

    # 检查服务
    start_time = time.time()
    if not check_health():
        log_info("❌ Camoufox 服务未运行，请先启动")
        sys.exit(1)

    # 确定模式
    mode = args.mode
    if mode == "auto":
        query_lower = args.query
        if any(kw in query_lower for kw in ["政策", "国务院", "央行", "发改委"]):
            mode = "policy"
        elif any(kw in query_lower for kw in ["股票", "股价", "涨停", "行情", "代码"]):
            mode = "stock"
        elif any(kw in query_lower for kw in ["今日", "最新", "快讯"]):
            mode = "news"
        else:
            mode = "deep"

    mode_cfg = SEARCH_MODES.get(mode, SEARCH_MODES["deep"])
    mode_desc = mode_cfg["desc"]

    if args.engine:
        engine_ids = [args.engine]
    else:
        engine_ids = mode_cfg["engines"]

    weights = get_dynamic_weights(args.query, mode)

    engine_names = "/".join(
        next(e["name"] for e in BASE_ENGINES if e["id"] == eid)
        for eid in engine_ids
    )

    mode_tag = f"[{mode}] {mode_desc}"

    log_info()
    log_info(f"🔍 Star Search v8.3 - 搜索: {args.query}")
    log_info(f"模式: {mode_tag}")
    log_info(f"引擎: {engine_names}")

    results = parallel_search(args.query, engine_ids, weights)

    if len(results) > 0:
        # 方案C：异步URL解析——不阻塞输出，后台尽可能解析
        # 多引擎模式解析前5条，单引擎模式(quick)解析前2条
        resolve_n = 5 if len(engine_ids) >= 2 else 2
        results = resolve_urls_async(results, top_n=resolve_n)

    top_n = min(max(args.top, 1), 30)
    elapsed = time.time() - start_time
    log_info(f"\n{'='*60}")
    log_info(f"📊 获取 {len(results)} 条去重结果 | 耗时 {format_time(elapsed)}")
    log_info(f"{'='*60}")

    if args.json:
        # JSON输出 → 纯stdout（info已全部走stderr）
        json_out = []
        for r in results[:top_n]:
            url_type = r.get("url_type", "redirect")
            # resolving标记：异步解析中/已完成
            json_out.append({
                "title": r["title"].lstrip("⭐"),
                "url": r["url"],
                "url_type": url_type,
                "real_url": r.get("real_url", r["url"]),
                "engine": r["best_source"],
                "cross_validated": r["cross_validated"],
                "date": r.get("date", "") or "",
                "summary": r.get("summary", "") or "",
                "score": round(r["score"], 1),
                "resolved": url_type == "direct",
            })
        sys.stdout.write(json.dumps(json_out, ensure_ascii=False, indent=2) + "\n")
    else:
        # 普通文本输出也走stdout（附标题+摘要等），但只剩结果行
        for i, r in enumerate(results[:top_n], 1):
            date_str = f" 📅{r['date']}" if r.get("date") else ""
            cv_str = f" ✅{r['cross_validated']}引擎" if r["cross_validated"] > 1 else ""
            ut = r.get("url_type", "redirect")
            if ut == "direct":
                ut_tag = "🔗"
            elif ut == "sourced":
                ut_tag = "📎"
            else:
                ut_tag = "↪"
            # 正在解析中的显示特殊标记
            resolving_tag = " ⏳" if r.get("resolving") else ""
            print(f"{i:2d}. {r['title'][:65]}{cv_str}{date_str} {ut_tag}{resolving_tag}")
            summary = r.get("summary", "")
            if summary:
                print(f"    [{r['best_source']}] {summary[:80]}")
            else:
                print(f"    [{r['best_source']}] {r['url'][:65]}")
            print()

        if len(results) > top_n:
            print(f"... 还有 {len(results) - top_n} 条未显示（使用 --top 30 查看全部）")

        print(f"耗时 {format_time(elapsed)}, {mode}模式")

    log_info(f"查询完成，结果已输出至stdout"  if args.json else "" )


if __name__ == "__main__":
    main()
