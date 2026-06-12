"""Systematic network diagnostics for news source connectivity."""
import os
import socket
import requests
import sys
import json

results = []
def log(msg):
    results.append(msg)
    print(msg, flush=True)

log("=" * 60)
log("1. 代理环境变量检查")
log("=" * 60)
found_proxy = False
for var in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']:
    val = os.environ.get(var, '')
    if val:
        log("  %s=%s" % (var, val))
        found_proxy = True
if not found_proxy:
    log("  - 无代理环境变量设置")
    log("  - requests 将使用直接连接")

log("")
log("=" * 60)
log("2. 系统代理设置 (Windows Registry)")
log("=" * 60)
try:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if proxy_enable:
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            log("  Windows 系统代理已启用: %s" % proxy_server)
        else:
            log("  Windows 系统代理: 未启用")
except Exception as e:
    log("  读取注册表失败: %s" % str(e)[:60])

log("")
log("=" * 60)
log("3. DNS 解析诊断")
log("=" * 60)
domains = [
    ("hacker-news.firebaseio.com", "Hacker News API"),
    ("feeds.arstechnica.com", "Ars Technica RSS"),
    ("www.technologyreview.com", "MIT Tech Review"),
    ("techcrunch.com", "TechCrunch RSS"),
    ("www.wired.com", "Wired RSS"),
    ("www.reddit.com", "Reddit API"),
    ("newsapi.org", "NewsAPI"),
    ("feeds.bbci.co.uk", "BBC RSS"),
    ("api.deepseek.com", "DeepSeek API"),
]
for domain, desc in domains:
    try:
        results_dns = socket.getaddrinfo(domain, 443)
        ip = results_dns[0][4][0]
        log("  %-35s %-25s IP: %s" % (domain, desc, ip))
    except socket.gaierror as e:
        log("  %-35s %-25s DNS FAILED: %s" % (domain, desc, str(e)[:40]))

log("")
log("=" * 60)
log("4. HTTP 可达性测试 (timeout=8s, 直接连接)")
log("=" * 60)
socket.setdefaulttimeout(8)
session = requests.Session()
session.trust_env = False  # Ignore proxy env vars - test direct connection

urls = [
    ("hacker_news_top", "https://hacker-news.firebaseio.com/v0/topstories.json"),
    ("hacker_news_item", "https://hacker-news.firebaseio.com/v0/item/1.json"),
    ("ars_technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("mit_tech_review", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    ("techcrunch", "https://techcrunch.com/feed/"),
    ("wired", "https://www.wired.com/feed/rss"),
    ("reddit", "https://www.reddit.com/r/technology/hot/.json"),
    ("newsapi_no_key", "https://newsapi.org/v2/everything?q=AI"),
    ("deepseek_models", "https://api.deepseek.com/v1/models"),
]

for name, url in urls:
    try:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        if "reddit" in name:
            ua = "AI-News-Agent/1.0"
        headers = {"User-Agent": ua}
        r = session.get(url, headers=headers, timeout=8)
        log("  [%-20s] HTTP %d (%d bytes)" % (name, r.status_code, len(r.content)))
    except requests.exceptions.ConnectTimeout:
        log("  [%-20s] ERROR: 连接超时 (TCP connect)" % name)
    except requests.exceptions.ReadTimeout:
        log("  [%-20s] ERROR: 响应超时 (server slow)" % name)
    except requests.exceptions.ConnectionError as e:
        err = str(e)[:80]
        log("  [%-20s] ERROR: 连接失败: %s" % (name, err))
    except Exception as e:
        log("  [%-20s] ERROR: %s" % (name, str(e)[:80]))

log("")
log("=" * 60)
log("5. Python requests 代理自动检测")
log("=" * 60)
log("  session.trust_env = %s" % session.trust_env)
log("  requests默认读取 HTTP_PROXY/HTTPS_PROXY 环境变量")
log("  Windows 系统代理不会自动被 requests 使用")
log("  需要在代码中显式配置 proxies 参数或设置环境变量")
log("")
log("  修复方案: 在代码中添加代理支持")
log("  1. 设置环境变量: set HTTPS_PROXY=http://127.0.0.1:7890")
log("  2. 或在代码中传递 proxies={\"https\": \"http://127.0.0.1:7890\"}")

log("")
log("=== 诊断完成 ===")

# Write to file for complete capture
out_path = r"c:\Users\H\Documents\trae_projects\news\diag_results.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
