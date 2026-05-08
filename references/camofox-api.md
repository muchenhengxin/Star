# Star Search — Camofox API Quick Reference

## Verified Working Endpoints (2026-05-08)

```bash
# Health check
curl http://localhost:9377/health
# → {"ok":true,"browserConnected":true,"engine":"camoufox"}

# Create tab + navigate
curl -s -X POST http://localhost:9377/tabs \
  -H "Content-Type: application/json" \
  -d '{"userId":"search","sessionKey":"'$RANDOM'","url":"https://www.baidu.com/s?wd='$(python3 -c "import urllib.parse; print(urllib.parse.quote('关键词'))")'"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tabId'])"

# Get snapshot (contains h3 headings with URLs)
curl -s "http://localhost:9377/tabs/$TAB_ID/snapshot?userId=search"

# Extract results from snapshot (Python regex)
python3 -c "
import re, sys
data = sys.stdin.read()
results = re.findall(r'heading \"(.*?)\" \[level=3\]:.*?/url: (http://www\.baidu\.com/link\?url=[^\s\)]+)', data)
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

## Engine Comparison

| Engine | Results | URL Quality | Captcha | Notes |
|--------|---------|-------------|---------|-------|
| Baidu+Camofox | 9 | ✅ Real URL | ✅ None | Best quality, PC content |
| 360+Camofox | 7 | ⚠️ Short link | ✅ None | `so.com/link?m=` inaccessible |
| Shenma+Camofox | 4 | ✅ Real URL | ✅ None | Mobile page, ads |
| Quark+Camofox | 0 | — | — | Dictionary redirect, unusable |
| Baidu (Hermes browser) | 0 | — | ❌ | Wrong browser, captcha |

## Key Files

- Skill: `~/.hermes/skills/research/web-search/SKILL.md`
- Dev log: `~/.hermes/skills/research/star-search-development-log/SKILL.md`
- Camofox: `/tmp/camofox-browser/`
- Browser cache: `~/Library/Caches/camoufox/`
