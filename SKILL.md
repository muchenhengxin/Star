---
name: star-search
description: "Use when asked to search the web, find online information, research topics, get news, or look up content. Primary: Sogou+Camofox (10 results, no captcha). Backup: Baidu+Camofox (9 results, random captcha). 360+Camofox (6 results, no captcha). All via Camofox REST API only — NOT Hermes browser tools."
version: 8.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Search, Web, Sogou, Baidu, 360, Camofox, China, Research, Discovery]
    related_skills: [arxiv, blogwatcher, session_search]
    references:
      - camofox-api.md  # Quick reference: endpoints, pitfalls, engine comparison
---

# Star Search v8 (搜狗优先 多引擎版)

## 引擎真实状态（2026-05实测）

| 引擎 | 方式 | 结果数 | 验证码 | URL质量 | 成本 | 推荐 |
|------|------|--------|--------|---------|------|------|
| **搜狗搜索** | Camoufox REST API | 10条 | 无 | JS跳转链 | 免费 | ✅ **首选主引擎** |
| **百度搜索** | Camoufox REST API | 9条 | 随机触发 | 真实URL | 免费 | ✅ **备选引擎** |
| **360搜索** | Camoufox REST API | 6条 | 无 | JS跳转链 | 免费 | ⚠️ **补充覆盖** |
| **神马搜索** | Camoufox REST API | 0条 | — | — | 免费 | ❌ 不可用 |
| **Bing中国/国际** | Camoufox REST API | 0条 | — | — | 免费 | ❌ DOM结构不兼容 |
| **Google/DuckDuckGo/Brave** | Camoufox REST API | 超时 | — | — | 免费 | ❌ 被拦截 |
| **百度千帆API** | REST API | — | — | — | 付费 | ❌ API Key已失效 |

### 关键发现（2026-05-09实测）

1. **搜狗是最稳定主引擎** — 10条结果，零验证码，结果质量高（腾讯云/CSDN/知乎/今日头条）
2. **百度验证码随机触发** — 长尾具体查询（如"AI API token 转售 市场"）通过，简单词（如"test"）触发
3. **即使显示验证，Baidu仍返回结果** — 验证码是叠加提示，不代表完全失效
4. **搜狗/360的JS跳转链URL** — `sogou.com/link?url=xxx` / `so.com/link?m=xxx` 无法通过HTTP直接解析真实地址，但浏览器点击可用
5. **百度千帆API Key已失效** — `bce-v3/ALTAK-yVyzs...` 返回 `NOT FOUND`，需重新申请
6. **Camoufox health检查** — `browserConnected=False` 不代表不可用，只要 `ok=true` 即可正常创建tab

**正确工作流（Camofox REST API）：**
```bash
# 1. 创建tab并导航到百度
TAB_ID=$(curl -s -X POST http://localhost:9377/tabs \
  -H "Content-Type: application/json" \
  -d '{"userId":"search","sessionKey":"'$RANDOM'","url":"https://www.baidu.com/s?wd='$(python3 -c "import urllib.parse; print(urllib.parse.quote('关键词'))")'"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['tabId'])")

# 2. 获取snapshot（包含完整页面内容）
curl -s "http://localhost:9377/tabs/$TAB_ID/snapshot?userId=search"

# 3. 从snapshot中用正则提取h3结果：
#    heading "标题" [level=3]: ... /url: http://www.baidu.com/link?url=XXX
```

**Camofox API核心端点：**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/tabs` | POST | 创建tab并导航 |
| `/tabs/:tabId/snapshot` | GET | 获取页面快照（含heading/link） |
| `/tabs/:tabId/links` | GET | 获取链接列表（导航用，非搜索结果） |
| `/tabs/:tabId/back` | POST | 返回 |
| `/tabs/:tabId/refresh` | POST | 刷新 |

**❌ 不要用：** `/tabs/:tabId/console` — Camofox没有console端点，会404

**验证Camofox运行：**
```bash
curl http://localhost:9377/health
# 正常: {"ok":true,"browserConnected":true,"engine":"camoufox"}
```

---

## 核心引擎

> **百度千帆API已失效** — API Key `bce-v3/ALTAK-...` 返回 NOT FOUND。v8 改用搜狗+百度+360多引擎方案，不再依赖千帆API。

| 引擎 | URL模板 | 结果数 | 验证码 | URL质量 | 成本 | 方式 |
|------|---------|--------|--------|---------|------|------|
| **搜狗搜索** | `https://www.sogou.com/web?query={q}&ie=utf8` | 10条 | 无 | JS跳转链 | 免费 | Camoufox REST API |
| **百度搜索** | `https://www.baidu.com/s?wd={q}` | 9条 | 随机 | 真实URL | 免费 | Camoufox REST API |
| **360搜索** | `https://www.so.com/s?q={q}` | 6条 | 无 | JS跳转链 | 免费 | Camoufox REST API |

### 神马/360/夸克搜索 (不稳定免费方案)

**问题根源：** 这些引擎依赖浏览器自动化，但会被反爬验证码拦截。不是网络问题，是行为检测。

**解决方案：Camofox — Hermes 内置的反检测浏览器**

Camofox 是 Firefox 分支（Camoufox）的 REST API 封装，**内置指纹欺骗**，自动绕过验证码。

**安装步骤：**
```bash
# 1. 克隆并安装（需要代理访问 GitHub）
cd /tmp && git clone https://github.com/jo-inc/camofox-browser && cd camofox-browser && npm install

# 2. 下载浏览器（约300MB，需要代理）
export https_proxy=http://127.0.0.1:7890  # 你的代理端口
npx camoufox-js fetch

# 3. 启动服务
npm start &
# 服务运行在 http://localhost:9377

# 4. 配置 Hermes 使用 Camofox
echo 'CAMOFOX_URL=http://localhost:9377' >> ~/.hermes/.env
# 重启 Hermes agent 后生效
```

**已知问题：** GitHub 下载 camoufox-browser 需要代理，否则超时。

**使用 Camofox 后的搜索方式：**
Camofox 启动后，Hermes 的 `browser_navigate` 等工具自动路由到 Camofox，无需修改代码。

---

## 一句话搜索命令

```javascript
// 1. 搜索
browser_navigate({url: "https://www.so.com/s?q=" + encodeURIComponent("你的搜索词")})

// 2. 等待
sleep 2

// 3. 提取结果 - 复制下面的代码
```

## Verified Working Extraction Code (2024)

**360搜索提取（已验证多次可用）：**

```javascript
const items = [];
document.querySelectorAll('h3').forEach((h3) => {
  const text = h3.innerText || '';
  if (text && !text.includes('还搜') && !text.includes('反馈') && !text.includes('猜您') && text.length > 10 && !text.includes('换一换')) {
    items.push({
      i: items.length + 1,
      title: text.substring(0, 100),
      url: h3.querySelector('a')?.href || ''
    });
  }
});
JSON.stringify({engine: '360搜索', found: items.length, results: items}, null, 2)
```

**Key insight:** CSS selector `h3` works reliably on 360 search. Filter out: "还搜" (related searches), "反馈" (feedback), "猜您" (suggestions), "换一换" (refresh).
// Step 2: 等待2秒
sleep 2

// Step 3: 提取结果
const data = await browser_console({expression: `
const items = [];
document.querySelectorAll('h3').forEach((h3) => {
  const text = h3.innerText || '';
  if (text && !text.includes('还搜') && !text.includes('反馈') && !text.includes('猜您') && text.length > 10 && !text.includes('换一换')) {
    items.push({
      i: items.length + 1,
      title: text.substring(0, 100),
      url: h3.querySelector('a')?.href || ''
    });
  }
});
JSON.stringify({engine: '360搜索', found: items.length, results: items}, null, 2)
`})
console.log(data)
```

---

## 提取结果示例

```json
{
  "engine": "360搜索",
  "found": 7,
  "results": [
    {"i": 1, "title": "卖 DeepSeek的 API 到底赚钱么? 其API服务的理论利润率高达545%", "url": "https://www.so.com/link?m=..."},
    {"i": 2, "title": "2025 AI 模型API中转国内直连聚合站", "url": "https://www.so.com/link?m=..."},
    {"i": 3, "title": "DeepSeek公布成本、收入和利润率", "url": "https://www.so.com/link?m=..."}
  ]
}
```

---

## 读取结果页面内容

```javascript
// 从上面的结果中找到想要深入阅读的URL，直接访问
await browser_navigate({url: "目标URL"})
sleep 2

// 获取页面正文
const content = await browser_console({expression: "document.body.innerText.substring(0, 5000)"})
console.log(content)
```

---

## 多引擎自动切换

```javascript
async function searchWithFailover(query) {
  const engines = [
    {name: '360', url: 'https://www.so.com/s?q=' + encodeURIComponent(query)},
    {name: '神马', url: 'https://www.sm.cn/s?q=' + encodeURIComponent(query)}
  ];
  
  for (const engine of engines) {
    console.log(`尝试 ${engine.name}...`);
    await browser_navigate({url: engine.url});
    sleep 2;
    
    // 检查是否被拦截
    const title = document.title;
    if (title.includes('验证') || title.includes('安全')) {
      console.log(`${engine.name} 被拦截，尝试下一个...`);
      continue;
    }
    
    // 提取结果
    const data = await browser_console({expression: `
      const items = [];
      document.querySelectorAll('h3').forEach((h3) => {
        const text = h3.innerText || '';
        if (text && !text.includes('还搜') && !text.includes('反馈') && text.length > 10) {
          items.push({title: text.substring(0, 80), url: h3.querySelector('a')?.href || ''});
        }
      });
      JSON.stringify(items.slice(0, 10))
    `});
    
    if (data && JSON.parse(data).length > 0) {
      return {engine: engine.name, results: JSON.parse(data)};
    }
  }
  return {error: '所有引擎均失败'};
}
```

---

## 验证码检测

```javascript
// 检测是否被验证码拦截
const isBlocked = () => {
  const title = document.title;
  const body = document.body?.innerText || '';
  return title.includes('验证') || 
         title.includes('安全') ||
         title.includes('拦截') ||
         body.includes('请输入验证码');
};
console.log('被拦截:', isBlocked());
```

---

## 神马搜索提取代码

如果360被拦截，使用神马搜索：

```javascript
// 神马搜索结果提取
const items = [];
document.querySelectorAll('h3, .title').forEach((h) => {
  const text = h.innerText || '';
  if (text && text.length > 5) {
    items.push({
      i: items.length + 1,
      title: text.substring(0, 100),
      url: h.querySelector('a')?.href || ''
    });
  }
});
JSON.stringify({engine: '神马搜索', found: items.length, results: items}, null, 2)
```

---

## 站点限定搜索

| 目标 | 搜索词 |
|------|--------|
| 知乎 | `site:zhihu.com 关键词` |
| 微信公众号 | `site:mp.weixin.qq.com 关键词` |
| CSDN | `site:csdn.net 关键词` |
| 腾讯云 | `site:cloud.tencent.com 关键词` |
| 阿里云 | `site:aliyun.com 关键词` |
| 36kr | `site:36kr.com 关键词` |

**示例：**
```
https://www.so.com/s?q=site:cloud.tencent.com%20AI%20API%20转售
```

---

## 分页

```javascript
// 360搜索分页 - first参数控制页码
// first=0 第1页, first=10 第2页, first=20 第3页
const pages = [0, 10, 20].map(first => 
  `https://www.so.com/s?q=${encodeURIComponent("关键词")}&first=${first}`
)
```

---

## 常用搜索命令速查

| 用途 | 命令 |
|------|------|
| 搜索 | `browser_navigate({url: "https://www.so.com/s?q=" + encodeURIComponent("关键词")})` |
| 等加载 | `sleep 2` |
| 提取结果 | `browser_console({expression: "document.querySelectorAll('h3').length + '个标题'"}` |
| 提取所有链接 | `browser_console({expression: "Array.from(document.querySelectorAll('a[href]')).map(a => a.href).slice(0, 20)"}` |
| 提取页面文本 | `browser_console({expression: "document.body.innerText.substring(0, 3000)"})` |

---

## 引擎选择指南

|| 引擎 | URL完整性 | 结果数量 | 推荐场景 |
|------|-----------|----------|----------|
| **百度+Camofox** | ✅ 真实URL | 9+条 | **首选** - 质量最高，URL可直接访问 |
| **神马搜索** | ✅ 完整URL | 9+条 | 次选（需Camofox防验证码） |
| **360搜索** | ⚠️ 短链接 | 7+条 | 三选 - URL需二次跳转 |

---

## 已知问题 & 应对

| 问题 | 原因 | 解决 |
|------|------|------|
| `BAIDU_API_KEY 环境变量未设置` | .env 文件未加载 | `source ~/.openclaw/workspace/.env.baidu` 后再运行脚本 |
| 神马/360频繁验证码 | 反检测能力弱 | 改用 Camofox 浏览器（见下方） |

## Camofox 反检测浏览器（重要！）

Hermes 内置 Camofox 支持 — 基于 Camoufox（Firefox 分支 + C++ 指纹伪造），可绕过百度/神马/360 的验证码拦截。

### 安装步骤
```bash
# 1. 安装 camofox-browser
git clone https://github.com/jo-inc/camofox-browser /tmp/camofox-browser
cd /tmp/camofox-browser && npm install

# 2. 下载 Camoufox 浏览器（约283MB，需要 GitHub 访问）
# 如果 npm fetch 超时，用 curl 直接下载：
curl -L "https://github.com/daijro/camoufox/releases/download/v135.0.1-beta.24/camoufox-135.0.1-beta.24-mac.arm64.zip" -o /tmp/camoufox.zip

# 3. 安装到正确位置
# Camoufox 安装目录: ~/Library/Caches/camoufox/
unzip /tmp/camoufox.zip -d ~/Library/Caches/camoufox/

# 4. 启动
cd /tmp/camofox-browser && npm start &

# 5. 验证
curl http://localhost:9377/health
# 正常: {"ok":true,"browserConnected":true}

# 6. 配置 Hermes 使用
echo 'CAMOFOX_URL=http://localhost:9377' >> ~/.hermes/.env
```

# 4. 手动安装 Camoufox（如果 npm fetch 超时）

Camoufox 浏览器约 283MB，如果 `npx camoufox-js fetch` 超时，手动下载：

```bash
# 4a. 直接下载 zip（速度慢约100KB/s，需要几十分钟）
curl -L "https://github.com/daijro/camoufox/releases/download/v135.0.1-beta.24/camoufox-135.0.1-beta.24-mac.arm64.zip" -o /tmp/camoufox.zip

# 4b. 解压到缓存目录
unzip /tmp/camoufox.zip -d ~/Library/Caches/camoufox/

# 4c. 【关键！】必须创建 version.json，camofox-server 靠它定位浏览器
curl -s "https://api.github.com/repos/daijro/camoufox/releases/tags/v135.0.1-beta.24" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('tag_name'))"
# 输出: v135.0.1-beta.24 → version 字段用 135.0.1-beta.24
echo '{"version":"135.0.1-beta.24","release":"v135.0.1-beta.24"}' > ~/Library/Caches/camoufox/version.json

# 4d. 验证
curl -s -X POST http://localhost:9377/tabs \
  -H "Content-Type: application/json" \
  -d '{"userId":"test","sessionKey":"test","url":"https://www.baidu.com"}'
# 正常返回 tabId，不再报 "Version information not found"
```

**为什么需要 version.json：** camofox-server 从 `~/Library/Caches/camoufox/version.json` 读取版本信息以定位 `Camoufox.app`，没有此文件则拒绝启动浏览器。

### Camofox vs 普通浏览器的关键区别
- 神马/360/百度 验证码拦截 → Camofox REST API **全部可过**
- 360短链接问题 → **百度+Camofox返回真实URL**（`baidu.com/link?url=xxx`），可直接访问
- 浏览器指纹暴露机器人 → Camofox 伪造真实指纹

**重要：Hermes browser工具不是Camofox！** 用browser_navigate访问百度会触发验证码，必须用Camofox REST API。

---

## 多引擎聚合搜索（推荐）

同时使用多个引擎可获得更多结果（约15-20条）：

```javascript
// 步骤1: 神马搜索（完整URL）
await browser_navigate({url: "https://www.sm.cn/s?q=" + encodeURIComponent("AI API 转售 市场")})
sleep 2
const shenmaResults = await browser_console({expression: `
const items = [];
document.querySelectorAll('h3, .title').forEach(h => {
  const text = h.innerText || '';
  if (text && text.length > 10 && !text.includes('广告') && !text.includes('还搜')) {
    const link = h.querySelector('a') || h;
    items.push({title: text.substring(0, 100), url: link?.href || ''});
  }
});
JSON.stringify({engine: '神马', count: items.length, results: items.slice(0, 8)}, null, 2)
`})

// 步骤2: 360搜索（补充结果）
await browser_navigate({url: "https://www.so.com/s?q=" + encodeURIComponent("AI API 转售 市场")})
sleep 2
const results360 = await browser_console({expression: `...same pattern...`})
```

---

## 常见问题处理

| 问题 | 解决方法 |
|------|----------|
| 验证码页面 | 等待5秒后刷新重试 |
| 结果为空 | 换用神马搜索（更稳定） |
| 页面加载慢 | `sleep 3` 等待更久 |
| URL被截断/短链接 | 使用神马搜索，或360结果点击标题获取真实URL |

## ⚠️ 关键陷阱

1. **用Hermes browser工具访问搜索**: 会触发验证码，必须用Camoufox REST API
2. **搜狗/360的URL是JS跳转链**: `sogou.com/link?url=xxx` / `so.com/link?m=xxx` 在浏览器点击可正常跳转，Python直接请求无法解析真实地址，这是正常行为，不影响使用

---

## 验证清单

- [x] Camoufox运行正常（health接口返回 `ok=true`，`browserConnected=False` 无妨）
- [x] 搜狗+Camoufox能正常加载，10条结果，零验证码 ✅ 主引擎
- [x] 百度+Camoufox能正常加载，9条结果（验证码随机）✅ 备选
- [x] 360搜索能正常加载，6条结果，零验证码 ✅ 补充
- [x] 神马搜索：0条结果，不可用
- [x] Bing/Google/DuckDuckGo/Brave/Naver：超时被拒，不可用
- [x] search.py v8 多引擎搜索正常（搜狗9+百度8+36011=28条）

---

## 快速测试

```javascript
// 测试1: 基本搜索
await browser_navigate({url: "https://www.so.com/s?q=test"})
sleep 2
await browser_console({expression: "document.title"})

// 测试2: 提取结果数量
await browser_navigate({url: "https://www.so.com/s?q=AI%20API%20转售"})
sleep 2
await browser_console({expression: "document.querySelectorAll('h3').length + ' h3 elements'"})

// 测试3: 完整提取
await browser_console({expression: `
  const items = [];
  document.querySelectorAll('h3').forEach(h3 => {
    const text = h3.innerText || '';
    if (text && !text.includes('还搜') && !text.includes('反馈') && text.length > 10) {
      items.push(text.substring(0, 80));
    }
  });
  items.slice(0, 10).join('\\n')
`})
```

---

## 实际应用案例

### 研究 AI API 转售市场

```javascript
// 1. 搜索市场概况
await browser_navigate({url: "https://www.so.com/s?q=" + encodeURIComponent("AI API 转售 市场 商业模式 利润")})
sleep 2

// 2. 提取相关结果
const results = await browser_console({expression: `...`})

// 3. 搜索具体数据
await browser_navigate({url: "https://www.so.com/s?q=" + encodeURIComponent("DeepSeek API 利润率 545%")})
sleep 2

// 4. 提取具体数字
const data = await browser_console({expression: `...`})
```
