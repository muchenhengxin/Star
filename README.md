# Star Search

中文搜索引擎，通过 Camofox 反检测浏览器实现免费、无验证码的百度搜索。

## 特性

- 🔍 **百度搜索** - 9条高质量结果，含日期和摘要
- 🚫 **无验证码** - Camofox 指纹伪造，绕过百度反爬
- 📱 **真实URL** - 直接返回可访问的真实链接（非短链接）
- ⚡ **免费方案** - 无需 API Key，使用 Camofox 浏览器自动化
- 🔄 **多引擎支持** - 百度主引擎，360/神马备用

## 工作原理

```
用户搜索请求
    ↓
Camofox REST API (POST /tabs)
    ↓
百度搜索页面加载
    ↓
获取 Snapshot (GET /snapshot)
    ↓
正则提取 h3 标题 + URL
```

## 安装

### 前置依赖

1. **安装 Camofox 浏览器**
```bash
# 克隆项目
cd /tmp && git clone https://github.com/jo-inc/camofox-browser.git
cd camofox-browser && npm install

# 下载 Camoufox 浏览器（约 283MB）
export https_proxy=http://127.0.0.1:7890  # 你的代理端口
npx camoufox-js fetch

# 或手动下载
curl -L "https://github.com/daijro/camoufox/releases/download/v135.0.1-beta.24/camoufox-135.0.1-beta.24-mac.arm64.zip" \
  -o /tmp/camoufox.zip
unzip /tmp/camoufox.zip -d ~/Library/Caches/camoufox/

# 创建 version.json（必需）
echo '{"version":"135.0.1-beta.24","release":"v135.0.1-beta.24"}' \
  > ~/Library/Caches/camoufox/version.json

# 启动服务
cd /tmp/camofox-browser && npm start &
```

2. **验证 Camofox 运行**
```bash
curl http://localhost:9377/health
# 应返回: {"ok":true,"browserConnected":true,"engine":"camoufox"}
```

### Hermes Agent 安装

```bash
# 克隆到 skills 目录
cp -r star-search ~/.hermes/skills/research/star-search
```

## 使用方法

### 基本搜索

```bash
# 1. 创建 tab 并搜索
TAB_ID=$(curl -s -X POST http://localhost:9377/tabs \
  -H "Content-Type: application/json" \
  -d '{"userId":"search","sessionKey":"'$(date +%s)'","url":"https://www.baidu.com/s?wd='$(python3 -c "import urllib.parse; print(urllib.parse.quote('关键词'))")'"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tabId'])")

# 2. 等待加载
sleep 3

# 3. 获取结果
curl -s "http://localhost:9377/tabs/$TAB_ID/snapshot?userId=search"
```

### Python 提取示例

```python
import re
import requests

def search(query):
    # 创建 tab
    tab_resp = requests.post("http://localhost:9377/tabs", json={
        "userId": "search",
        "sessionKey": "test",
        "url": f"https://www.baidu.com/s?wd={query}"
    })
    tab_id = tab_resp.json()["tabId"]
    
    # 等待加载
    import time; time.sleep(3)
    
    # 获取 snapshot
    snap_resp = requests.get(f"http://localhost:9377/tabs/{tab_id}/snapshot", params={"userId": "search"})
    data = snap_resp.text
    
    # 提取结果
    pattern = r'heading "(.*?)" \[level=3\]:.*?/url: (http://www\.baidu\.com/link\?url=[^\s\)]+)'
    results = re.findall(pattern, data)
    
    return [{"title": t, "url": u} for t, u in results]

# 使用
for r in search("AI API 转售 市场"):
    print(f"- {r['title'][:50]}...")
```

## 引擎对比

| 引擎 | 结果数 | URL质量 | 验证码 | 推荐 |
|------|--------|---------|--------|------|
| **百度+Camofox** | 9条 | ✅ 真实URL | 无 | ✅ 首选 |
| 360搜索 | 7条 | ⚠️ 短链接 | 无 | 备用 |
| 神马搜索 | 4条 | ✅ 完整URL | 有 | 不推荐 |

## 已知问题

1. **必须用 Camofox REST API** - Hermes 的 browser_navigate 不是 Camofox，会触发验证码
2. **360 短链接** - `so.com/link?m=xxx` 格式无法直接访问
3. **夸克搜索不可用** - 搜索词会被词典功能拦截

## 技术栈

- [Camofox](https://github.com/jo-inc/camofox-browser) - 反检测浏览器 REST API
- [Camoufox](https://github.com/daijro/camoufox) - Firefox 分支 + C++ 指纹伪造

## License

MIT License
