"""
微信公众号文章搜索 (融合 wechat-article-search skill)
- 通过搜狗微信搜索获取公众号文章
- 解析真实 mp.weixin.qq.com 链接
- 反爬虫机制: 随机 UA + 搜狗 Cookie + 重试 + 随机延迟

用法:
    from wechat_search import search_wechat_articles
    articles = search_wechat_articles("华为", max_results=10, resolve_real_url=False)
"""
import sys
import os
import re
import json
import time
import gzip
import zlib
try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
import random
import urllib.request
import urllib.error
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from http.client import HTTPSConnection
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============ 1. UA 池 (20 个) ============

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/123.0.0.0 Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/122.0.0.0 Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; Mi 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
]


def get_random_ua():
    return random.choice(USER_AGENTS)


# ============ 2. HTTP 请求 (gzip/deflate/br 解压) ============

def decompress_body(data: bytes, content_encoding: Optional[str]) -> bytes:
    """解压 HTTP 响应体 (gzip/deflate/br)"""
    if not content_encoding:
        return data
    encoding = content_encoding.lower()
    try:
        if 'gzip' in encoding:
            return gzip.decompress(data)
        if 'deflate' in encoding:
            return zlib.decompress(data)
        if 'br' in encoding:
            if HAS_BROTLI:
                return brotli.decompress(data)
            # brotli 不可用, 返回原始数据
            return data
    except Exception:
        pass
    return data


def http_request(url: str, method: str = 'GET', headers: dict = None,
                 timeout: int = 15, max_retries: int = 0,
                 allow_redirects: bool = True) -> Dict:
    """
    统一 HTTP 请求 - 支持 gzip/deflate/br 解压
    返回: {status_code, headers, body (bytes)}
    """
    headers = headers or {}
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != 'https':
                raise ValueError(f"only https supported, got {parsed.scheme}")

            conn = HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout)
            path = parsed.path
            if parsed.query:
                path += '?' + parsed.query

            # 处理 Set-Cookie 多值头 (Python 内部用 list 接收)
            req_headers = dict(headers)
            conn.request(method, path, headers=req_headers)
            resp = conn.getresponse()

            # 读取 body
            raw = resp.read()

            # 解压
            content_encoding = resp.getheader('Content-Encoding', '')
            body = decompress_body(raw, content_encoding)

            # 收集 headers
            resp_headers = {}
            set_cookies = []
            for name, value in resp.getheaders():
                name_lower = name.lower()
                if name_lower == 'set-cookie':
                    set_cookies.append(value)
                else:
                    resp_headers[name] = value

            if set_cookies:
                resp_headers['set-cookie'] = set_cookies

            conn.close()

            return {
                'status_code': resp.status,
                'headers': resp_headers,
                'body': body,
            }

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(0.3 + attempt * 0.3)
            else:
                raise RuntimeError(f"Request failed: {method} {url}: {last_error}")

    raise RuntimeError(f"Request failed: {method} {url}: unexpected")


def http_get_text(url: str, headers: dict = None, timeout: int = 30,
                  max_retries: int = 1) -> Dict:
    """GET 请求并返回 text + 元信息"""
    resp = http_request(url, headers=headers, timeout=timeout, max_retries=max_retries)
    return {
        **resp,
        'text': resp['body'].decode('utf-8', errors='ignore'),
    }


# ============ 3. Cookie 处理 ============

def extract_cookies(headers: dict) -> str:
    """从响应头提取 cookie 字符串"""
    cookies = []
    set_cookie_header = headers.get('set-cookie', [])
    if isinstance(set_cookie_header, str):
        set_cookie_header = [set_cookie_header]

    for cookie in set_cookie_header:
        cookie_value = cookie.split(';')[0]
        if cookie_value:
            cookies.append(cookie_value)
    return '; '.join(cookies)


def parse_cookie_string(cookie_str: str) -> dict:
    """解析 cookie 字符串为 dict"""
    cookies = {}
    if not cookie_str:
        return cookies
    for cookie in cookie_str.split('; '):
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


# ============ 4. 搜狗微信 Cookie 初始化 ============

def get_sogou_cookie() -> dict:
    """从搜狗视频页面获取 cookie - 必须先访问, 才能搜微信文章"""
    try:
        resp = http_request(
            'https://v.sogou.com/v?ie=utf8&query=&p=40030600',
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'identity',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'User-Agent': get_random_ua(),
            },
            timeout=10,
            max_retries=1,
        )
        cookie_str = extract_cookies(resp['headers'])
        return {
            'cookie_str': cookie_str or '',
            'cookie_obj': parse_cookie_string(cookie_str),
        }
    except Exception:
        return {'cookie_str': '', 'cookie_obj': {}}


# ============ 5. HTTP GET 主请求 ============

DEFAULT_SEARCH_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'identity',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Host': 'weixin.sogou.com',
    'Referer': 'https://weixin.sogou.com/',
}


def http_get(url: str, cookie_str: str = '') -> str:
    """GET 请求 + cookie"""
    headers = dict(DEFAULT_SEARCH_HEADERS)
    headers['User-Agent'] = get_random_ua()
    if cookie_str:
        headers['Cookie'] = cookie_str

    resp = http_get_text(url, headers=headers, timeout=30, max_retries=1)
    return resp['text']


# ============ 6. HTML 解析 - 轻量级 (无依赖) ============

class ArticleListParser(HTMLParser):
    """解析搜狗微信搜索结果 ul.news-list2 > li"""

    def __init__(self):
        super().__init__()
        self.articles = []
        self.current_article = None
        self.current_field = None
        self.current_text = ''
        self.depth = 0
        self.in_li = False
        self.in_news_list = False
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'script':
            self.in_script = True
            return

        if tag == 'ul' and attrs_dict.get('class') == 'news-list':
            self.in_news_list = True
            return

        if tag == 'li' and self.in_news_list:
            self.in_li = True
            self.current_article = {
                'title': '',
                'url': '',
                'summary': '',
                'datetime': '',
                'date_text': '',
                'date_description': '',
                'source': '',
                'time_description': '',
            }
            self.depth = 0
            return

        if self.in_li and self.current_article is not None:
            self.depth += 1
            cls = attrs_dict.get('class', '')
            href = attrs_dict.get('href', '')

            # 标题
            if tag == 'a' and self.depth == 2:  # h3 > a
                if href:
                    self.current_article['url'] = href

            # 概要
            if tag == 'p' and 'txt-info' in cls:
                self.current_field = 'summary'

            # 来源
            if cls == 's-p':
                self.current_field = '_source_box'

            # 标题文字
            if tag == 'h3':
                self.current_field = 'title'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False
            return
        if tag == 'ul' and self.in_news_list:
            self.in_news_list = False
            return
        if tag == 'li' and self.in_li:
            if self.current_article:
                self.articles.append(self.current_article)
            self.current_article = None
            self.in_li = False
            self.depth = 0
            return

        if self.in_li and self.current_article is not None:
            self.depth -= 1

        if tag in ('p', 'h3') and self.current_field:
            text = self.current_text.strip()
            if self.current_field == 'title':
                self.current_article['title'] = text
            elif self.current_field == 'summary':
                self.current_article['summary'] = text
            elif self.current_field == '_source_box' and tag == 'p':
                # 解析来源盒子
                pass
            self.current_field = None
            self.current_text = ''

    def handle_data(self, data):
        if self.in_script:
            return
        if self.in_li and self.current_field:
            self.current_text += data

        # 在 source box 内捕获来源
        if self.in_li and self.current_article is not None:
            if self.current_field == '_source_box' and data.strip():
                if not self.current_article['source']:
                    # 尝试捕获来源 (公众号名)
                    text = data.strip()
                    if text and len(text) < 30:
                        self.current_article['source'] = text


# 更简单的解析方式 - 用正则
def parse_articles_with_regex(html: str, max_results: int) -> List[dict]:
    """
    用正则解析 ul.news-list > li
    失败则用 HTMLParser 兜底
    """
    articles = []

    # 匹配 ul.news-list
    ul_match = re.search(r'<ul[^>]*class=["\']news-list["\'][^>]*>(.*?)</ul>', html, re.DOTALL)
    if not ul_match:
        return articles

    ul_html = ul_match.group(1)

    # 找每个 li
    li_pattern = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL)
    for li_match in li_pattern.finditer(ul_html):
        li_html = li_match.group(1)
        article = parse_single_article(li_html)
        if article:
            articles.append(article)
            if len(articles) >= max_results:
                break

    return articles


def parse_single_article(li_html: str) -> Optional[dict]:
    """解析单个 li 中的文章"""
    # 标题 + URL: <h3>...<a href="...">title</a></h3>
    title_match = re.search(r'<h3[^>]*>.*?<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', li_html, re.DOTALL)
    if not title_match:
        return None

    url = title_match.group(1).strip()
    title = re.sub(r'\s+', ' ', title_match.group(2).strip())

    # 处理相对 URL
    if url.startswith('/'):
        url = 'https://weixin.sogou.com' + url

    # 概要: <p class="txt-info">...</p>
    summary_match = re.search(r'<p[^>]*class=["\']txt-info["\'][^>]*>(.*?)</p>', li_html, re.DOTALL)
    summary = ''
    if summary_match:
        summary = re.sub(r'<[^>]+>', ' ', summary_match.group(1)).strip()
        summary = re.sub(r'\s+', ' ', summary)

    # 来源盒子 .s-p
    source_box_match = re.search(r'<p[^>]*class=["\']s-p["\'][^>]*>(.*?)</p>', li_html, re.DOTALL)
    source = ''
    datetime_str = ''
    date_text = ''
    time_desc = ''

    if source_box_match:
        sb = source_box_match.group(1)

        # 时间戳: <script>document.write(timeConvert(...))</script>
        script_match = re.search(r'<script[^>]*>(.*?)</script>', sb, re.DOTALL)
        if script_match:
            ts_match = re.search(r'timeConvert\((\d{10,13})\)', script_match.group(1))
            if ts_match:
                ts = int(ts_match.group(1))
                if ts > 9999999999:
                    ts //= 1000  # ms → s
                dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                date_text = dt.strftime('%Y年%m月%d日')

                # 相对时间描述
                now = datetime.now(tz=timezone(timedelta(hours=8)))
                diff = now - dt
                if diff.days > 0:
                    time_desc = f'{diff.days}天前'
                elif diff.seconds > 3600:
                    time_desc = f'{diff.seconds // 3600}小时前'
                elif diff.seconds > 60:
                    time_desc = f'{diff.seconds // 60}分钟前'
                else:
                    time_desc = '刚刚'

        # 来源: .all-time-y2 或 a.account
        source_match = re.search(r'<span[^>]*class=["\']all-time-y2["\'][^>]*>([^<]+)</span>', sb)
        if not source_match:
            source_match = re.search(r'<a[^>]*class=["\']account["\'][^>]*>([^<]+)</a>', sb)
        if source_match:
            source = source_match.group(1).strip()

    return {
        'title': title,
        'url': url,
        'summary': summary,
        'datetime': datetime_str,
        'date_text': date_text,
        'date_description': time_desc or date_text,
        'source': source,
    }


def parse_articles_from_search_html(html: str, max_results: int) -> List[dict]:
    """从搜狗搜索结果 HTML 解析文章列表"""
    return parse_articles_with_regex(html, max_results)


# ============ 7. 真实 URL 解析 (绕过 anti-bot) ============

def extract_redirect_url_from_html(html: str) -> Optional[str]:
    """从 HTML 中提取跳转 URL (meta refresh / JS location)"""
    # meta refresh
    meta_match = re.search(
        r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\']\d+;\s*url=([^"\']+)["\'][^>]*>',
        html, re.IGNORECASE)
    if meta_match:
        return meta_match.group(1)

    # JS location
    js_match = (re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', html) or
                re.search(r'location\s*=\s*["\']([^"\']+)["\']', html) or
                re.search(r'window\.location\s*=\s*["\']([^"\']+)["\']', html))
    if js_match:
        return js_match.group(1)

    # 拼接 url += '...' 模式
    url_parts = []
    for m in re.finditer(r'url\s*\+=\s*\'([^\']*)\'', html):
        url_parts.append(m.group(1))
    for m in re.finditer(r'url\s*\+=\s*"([^"]*)"', html):
        url_parts.append(m.group(1))

    if url_parts:
        joined = ''.join(url_parts)
        if 'mp.weixin.qq.com' in joined:
            return joined

    return None


def get_real_url(url: str, cookie_obj: dict = None, retries: int = 3) -> str:
    """
    获取搜狗跳转后的真实 URL (mp.weixin.qq.com)
    - 如果不是搜狗链接, 直接返回
    - 否则访问搜狗链接, 拿 Location 或 JS 跳转
    """
    if cookie_obj is None:
        cookie_obj = {}
    if 'weixin.sogou.com' not in url:
        return url

    base_cookies = 'ABTEST=7|1716888919|v1; IPLOC=CN5101; ariaDefaultTheme=default; ariaFixed=true; ariaReadtype=1; ariaStatus=false'
    snuid = cookie_obj.get('SNUID', '')
    cookie_str = f'{base_cookies}; SNUID={snuid}' if snuid else base_cookies

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cookie': cookie_str,
        'User-Agent': get_random_ua(),
    }

    for attempt in range(retries):
        try:
            resp = http_request(url, headers=headers, timeout=5, max_retries=0)

            # 检查 redirect
            if 300 <= resp['status_code'] < 400:
                location = resp['headers'].get('location', '')
                if 'mp.weixin.qq.com' in location:
                    return location
                return url

            if resp['status_code'] == 200:
                html = resp['body'].decode('utf-8', errors='ignore')
                real_url = extract_redirect_url_from_html(html)
                if real_url and 'mp.weixin.qq.com' in real_url:
                    return real_url
                return url

        except Exception:
            pass

        if attempt < retries - 1:
            time.sleep(1)

    return url


def resolve_real_urls(articles: List[dict]) -> List[dict]:
    """批量解析真实 URL"""
    cookie_info = get_sogou_cookie()
    cookie_obj = cookie_info['cookie_obj']

    results = []
    success_count = 0
    fail_count = 0

    print(f'获取到 {len(articles)} 篇文章，开始解析真实URL...')
    print('注意：搜狗微信有严格的反爬虫机制，可能无法获取真实URL')

    for i, article in enumerate(articles):
        try:
            real_url = get_real_url(article['url'], cookie_obj)
            is_success = ('weixin.sogou.com' not in real_url and 'antispider' not in real_url)

            new_article = dict(article)
            new_article['url'] = real_url if is_success else article['url']
            new_article['url_resolved'] = is_success
            results.append(new_article)

            if is_success:
                success_count += 1
            else:
                fail_count += 1

            if i < len(articles) - 1:
                time.sleep(0.5 + random.random())
        except Exception as e:
            print(f'  解析失败: {e}')
            new_article = dict(article)
            new_article['url_resolved'] = False
            results.append(new_article)
            fail_count += 1

    print(f'\n解析完成: 成功 {success_count}, 失败 {fail_count}')
    return results


# ============ 8. 主函数 - 搜索微信公众号文章 ============

def search_wechat_articles(query: str, max_results: int = 10,
                          resolve_real_url: bool = False) -> List[dict]:
    """
    主搜索函数 - 通过搜狗微信搜索公众号文章

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数 (默认 10, 最大 50)
        resolve_real_url: 是否解析真实微信 URL (会额外请求, 默认 False)

    Returns:
        文章列表 [{title, url, summary, datetime, date_text, source, ...}, ...]
    """
    max_results = min(max_results, 50)
    articles = []
    page = 1
    pages_needed = (max_results + 9) // 10  # 向上取整

    while len(articles) < max_results and page <= pages_needed:
        try:
            cookie_info = get_sogou_cookie()
            cookie_str = cookie_info['cookie_str']

            encoded_query = urllib.parse.quote(query)
            url = f'https://weixin.sogou.com/weixin?query={encoded_query}&s_from=input&_sug_=n&type=2&page={page}&ie=utf8'

            html = http_get(url, cookie_str)

            remaining = max_results - len(articles)
            parsed = parse_articles_from_search_html(html, remaining)
            if not parsed:
                break
            articles.extend(parsed)

            page += 1

            # 随机延迟避免过快
            if page <= pages_needed:
                time.sleep(0.5 + random.random())

        except Exception as e:
            print(f'请求第{page}页失败: {e}')
            break

    result = articles[:max_results]

    if resolve_real_url and result:
        print('正在解析真实URL...')
        return resolve_real_urls(result)

    return result


# ============ CLI 入口 ============

# ============ 9. mp.weixin.qq.com Cookie 方式 (来自 hermione) ============

import urllib.parse as _urlparse

def get_wechat_token(cookie: str, timeout: int = 10) -> Optional[str]:
    """从 mp.weixin.qq.com 拿 token (Cookie 登录)"""
    try:
        req = urllib.request.Request(
            'https://mp.weixin.qq.com/',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Cookie': cookie,
                'Referer': 'https://mp.weixin.qq.com/'
            }
        )
        # 不自动 follow redirect, 拿最终的 URL
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        resp = opener.open(req, timeout=timeout)

        parsed = _urlparse.urlparse(resp.url)
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        return params.get('token', [None])[0]
    except Exception as e:
        return None


def mp_search_fakeid(cookie: str, token: str, name: str,
                    timeout: int = 10) -> tuple:
    """mp.weixin.qq.com 搜公众号 - 返回 (fakeid, nickname)"""
    try:
        params = {
            'action': 'search_biz',
            'token': token,
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': '1',
            'random': str(time.time()),
            'query': name,
        }
        query_str = _urlparse.urlencode(params)
        url = f'https://mp.weixin.qq.com/cgi-bin/searchbiz?{query_str}'

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': cookie,
            'Referer': 'https://mp.weixin.qq.com/'
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())

        if data.get('base_resp', {}).get('ret') == 0 and data.get('list'):
            return data['list'][0]['fakeid'], data['list'][0]['nickname']
        return None, None
    except Exception as e:
        return None, None


def mp_get_article_list(cookie: str, token: str, fakeid: str,
                       count: int = 10, timeout: int = 10) -> list:
    """mp.weixin.qq.com 拿公众号文章列表"""
    try:
        params = {
            'action': 'list_ex',
            'token': token,
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': '1',
            'random': str(time.time()),
            'fakeid': fakeid,
            'type': '9',  # 9 = 全部
            'count': str(count),
            'begin': '0',
        }
        query_str = _urlparse.urlencode(params)
        url = f'https://mp.weixin.qq.com/cgi-bin/appmsg?{query_str}'

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': cookie,
            'Referer': 'https://mp.weixin.qq.com/'
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())

        if data.get('base_resp', {}).get('ret') == 0:
            return data.get('app_msg_list', [])
        return []
    except Exception as e:
        return []


def search_wechat_by_cookie(name: str, cookie: str, max_results: int = 10) -> list:
    """通过 Cookie 登录 mp.weixin.qq.com 搜公众号 + 拿文章列表"""
    token = get_wechat_token(cookie)
    if not token:
        return []

    fakeid, nickname = mp_search_fakeid(cookie, token, name)
    if not fakeid:
        return []

    articles = mp_get_article_list(cookie, token, fakeid, count=max_results)

    # 转成统一格式
    results = []
    for art in articles:
        # 时间戳: create_time 是 unix timestamp (seconds)
        ts = art.get('create_time', 0)
        if ts > 9999999999:
            ts //= 1000
        if ts > 0:
            dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
            datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            datetime_str = ''

        # 封面图
        cover = art.get('cover', '')
        # 内容 URL
        link = art.get('link', '')
        # 摘要
        digest = art.get('digest', '')

        results.append({
            'title': art.get('title', '').replace('<em>', '').replace('</em>', ''),
            'url': link,
            'summary': digest,
            'datetime': datetime_str,
            'date_text': '',
            'date_description': datetime_str,
            'source': nickname,
            'cover': cover,
            'method': 'mp.weixin.qq.com',
        })
        if len(results) >= max_results:
            break

    return results


# ============ 10. 统一入口 (智能选择最佳方法) ============

def search_wechat_smart(query: str, max_results: int = 10,
                       mp_cookie: str = None) -> dict:
    """
    智能微信公众号搜索
    - 如果提供 mp_cookie, 用 mp.weixin.qq.com (稳定, 需 Cookie)
    - 否则用搜狗微信搜索 (免配置, 但易被反爬)
    
    返回: {method, articles, error}
    """
    # 优先 mp.weixin.qq.com (如果有 Cookie)
    if mp_cookie:
        try:
            articles = search_wechat_by_cookie(query, mp_cookie, max_results)
            if articles:
                return {
                    'method': 'mp.weixin.qq.com',
                    'articles': articles,
                    'error': None,
                }
        except Exception as e:
            mp_error = str(e)
    else:
        mp_error = 'no cookie provided'

    # fallback 到搜狗
    try:
        articles = search_wechat_articles(query, max_results)
        if articles:
            return {
                'method': 'sogou.weixin',
                'articles': articles,
                'error': None,
            }
        return {
            'method': 'sogou.weixin',
            'articles': [],
            'error': '搜狗反爬: 多次请求后被重定向到 antispider 页面 (正常现象, 稍等几分钟再试)',
        }
    except Exception as e:
        return {
            'method': 'sogou.weixin',
            'articles': [],
            'error': str(e),
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='微信公众号文章搜索')
    parser.add_argument('query', help='搜索关键词')
    parser.add_argument('-n', '--num', type=int, default=10, help='返回数量 (最大 50)')
    parser.add_argument('-r', '--resolve-url', action='store_true', help='解析真实微信文章 URL')
    parser.add_argument('-o', '--output', help='输出 JSON 文件路径')
    args = parser.parse_args()

    print(f'正在搜索: "{args.query}"...')

    try:
        articles = search_wechat_articles(
            args.query,
            max_results=args.num,
            resolve_real_url=args.resolve_url,
        )

        result = {
            'query': args.query,
            'total': len(articles),
            'articles': articles,
        }

        output = json.dumps(result, ensure_ascii=False, indent=2)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f'结果已保存到: {args.output}')

        print(output)
    except Exception as e:
        print(f'搜索失败: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
