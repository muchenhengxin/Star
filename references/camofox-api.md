# Star Search — Camofox API Quick Reference

## Verified Working Endpoints (2026-05-09)

```bash
# Health check — ok=true is what matters, browserConnected=False is OK
curl http://localhost:9377/health
# → {"ok":true,"browserConnected":true,"engine":"camoufox"}
# → {"ok":true,"browserConnected":false,"engine":"camoufox"} ← also works!

# Create tab + navigate (works for: Sogou, Baidu, 360)
curl -s -X POST http://localhost:9377/tabs \
  -H "Content-Type: application/json" \
  -d '{"userId":"search","sessionKey":"'$RANDOM'","url":"https://www.sogou.com/web?query='$(python3 -c "import urllib.parse; print(urllib.parse.quote('关键词'))")'&ie=utf8"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tabId'])"

# Get snapshot (contains h3 headings with URLs)
curl -s "http://localhost:9377/tabs/$TAB_ID/snapshot?userId=search"

# Extract results from snapshot (Sogou — primary engine)
python3 -c "
import re, sys
data = sys.stdin.read()
# Sogou: level=3 headings + /link?url= paths
results = re.findall(r'heading \"(.*?)\" \[level=3\]:.*?/url: (/link\?url=[^\s\\]+)', data, re.DOTALL)
for i, (title, url) in enumerate(results, 1):
    print(f'{i}. {title}')
    print(f'   https://www.sogou.com{url}')
"

# Extract results from snapshot (Baidu — backup engine)
python3 -c "
import re, sys
data = sys.stdin.read()
# Baidu: level=3 headings + baidu.com/link?url= full URLs
results = re.findall(r'heading \"(.*?)\" \[level=3\]:.*?/url: (http://www\.baidu\.com/link\?url=[^\s\\)]+)', data)
for i, (title, url) in enumerate(results, 1):
    print(f'{i}. {title}')
    print(f'   {url}')
"
```

## Known Pitfalls

1. **Camofox REST API ≠ Hermes browser tools** — `browser_navigate` and `browser_console` are NOT Camofox. They use a different browser and trigger Baidu captcha.
2. **Use /snapshot only** — `/tabs/:tabId/console` does NOT exist on Camofox (404). Use `/snapshot` for content extraction.
3. **version.json required** — `~/Library/Caches/camoufox/version.json` must exist or Camoufox refuses to start.
4. **Quark (`quark.cn`) is broken** — Intercepts queries and redirects to dictionary. Use Baidu instead.

## Engine Comparison (2026-05-09 实测更新)

| Engine | Results | URL Quality | Captcha | Status |
|--------|---------|-------------|---------|--------|
| **Sogou+Camoufox** | 10 | ⚠️ JS redirect chain | ✅ None | ✅ Best - primary engine |
| **Baidu+Camoufox** | 9 | ✅ Real URL | ⚠️ Random | ✅ Backup engine |
| **360+Camoufox** | 6 | ⚠️ JS redirect chain | ✅ None | ⚠️ Supplementary |
| Shenma+Camoufox | 0 | — | — | ❌ Unusable |
| Bing+Camoufox | 0 | — | — | ❌ DOM incompatible |
| Google/DDG/Brave | timeout | — | — | ❌ Blocked |
| Baidu Qianfan API | — | — | — | ❌ API Key expired |

## Result Extraction Regex Patterns

**Sogou** (primary engine — 10 results, no captcha):
```python
pattern = r'heading "([^"]+)" \[level=3\]:.*?/url: (/link\?url=[^\s\\]+)'
matches = re.findall(pattern, snap, re.DOTALL)
```

**Baidu** (backup engine — 9 results, random captcha):
```python
pattern = r'heading "([^"]+)" \[level=3\]:.*?/url: (http://www\.baidu\.com/link\?url=[^\s\\)]+)'
```

**360** (supplementary — 6 results, no captcha):
```python
pattern = r'heading "([^"]+)" \[level=3\]:'
# 360 URLs are so.com/link?m=xxx — JS redirect chain, cannot resolve via HTTP
```

## Known Pitfalls

1. **Camoufox REST API ≠ Hermes browser tools** — `browser_navigate` and `browser_console` are NOT Camoufox. They use a different browser and trigger Baidu captcha.
2. **Use /snapshot only** — `/tabs/:tabId/console` does NOT exist on Camoufox (404). Use `/snapshot` for content extraction.
3. **version.json required** — `~/Library/Caches/camoufox/version.json` must exist or Camoufox refuses to start.
4. **Quark (`quark.cn`) is broken** — Intercepts queries and redirects to dictionary. Use Sogou instead.
5. **Baidu Qianfan API Key expired** — `bce-v3/ALTAK-...` returns `NOT FOUND`. No fix needed since Camoufox+Sogou works.
6. **health `browserConnected=False` ≠ unavailable** — As long as `ok=true`, tab creation works.
7. **Sogou/360 URLs are JS redirect chains** — `sogou.com/link?url=xxx` and `so.com/link?m=xxx` cannot be resolved by direct HTTP. They work in real browser context.
