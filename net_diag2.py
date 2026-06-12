"""Diagnose each news source individually with shorter timeout."""
import socket, requests, time, sys, os

# Set timeouts globally
socket.setdefaulttimeout(8)
s = requests.Session()

urls = [
    ('HN_API',      'https://hacker-news.firebaseio.com/v0/topstories.json', 6),
    ('Ars_Technica','https://feeds.arstechnica.com/arstechnica/index', 6),
    ('MIT_Tech_Rev','https://www.technologyreview.com/topic/artificial-intelligence/feed/', 6),
    ('TechCrunch',  'https://techcrunch.com/feed/', 6),
    ('Wired',       'https://www.wired.com/feed/rss', 6),
    ('Reddit',      'https://www.reddit.com/r/technology/hot/.json', 8),
    ('DeepSeek_API','https://api.deepseek.com/v1/models', 6),
]

out = []
def log(msg):
    out.append(msg)
    print(msg, flush=True)

log("=" * 60)
log("News Source Connectivity Diagnostics (individual)")
log("=" * 60)

for name, url, timeout in urls:
    t0 = time.time()
    try:
        hdrs = {'User-Agent': 'AI-News-Agent/1.0'}
        if 'reddit' in name:
            hdrs['User-Agent'] = 'AI-News-Agent/1.0 (by /u/news_agent_bot)'
        r = s.get(url, headers=hdrs, timeout=timeout)
        ms = int((time.time()-t0)*1000)
        log(f"[OK] {name:15s} | HTTP {r.status_code}  {ms}ms  ({len(r.content)} bytes)")
    except requests.Timeout:
        ms = int((time.time()-t0)*1000)
        log(f"[!!] {name:15s} | TIMEOUT after {ms}ms (limit: {timeout}s)")
    except requests.ConnectionError as e:
        ms = int((time.time()-t0)*1000)
        err = str(e)[:100]
        log(f"[!!] {name:15s} | CONN FAIL ({ms}ms): {err}")
    except Exception as e:
        ms = int((time.time()-t0)*1000)
        log(f"[!!] {name:15s} | ERROR ({ms}ms): {str(e)[:100]}")

log("")
log("=" * 60)
log("DNS Check")
log("=" * 60)
domains = ['hacker-news.firebaseio.com','feeds.arstechnica.com',
           'www.technologyreview.com','techcrunch.com','www.wired.com',
           'www.reddit.com','newsapi.org','api.deepseek.com']
for d in domains:
    try:
        ip = socket.getaddrinfo(d, 443)[0][4][0]
        log(f"  {d:40s} -> {ip}")
    except Exception as e:
        log(f"  {d:40s} -> FAIL: {str(e)[:50]}")

log("")
log("=" * 60)
log("Proxy Env")
log("=" * 60)
for var in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:
    val = os.environ.get(var,'')
    if val:
        log(f"  {var} = {val}")
    else:
        log(f"  {var} = (unset)")

# Try detect proxy port scan
log("")
log("Proxy Port Scan:")
for port in [7890, 10808, 1080, 7891, 10809]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        if result == 0:
            log(f"  127.0.0.1:{port} -> OPEN")
    except:
        pass

# Save to file
with open(r"c:\Users\H\Documents\trae_projects\news\net_diag_result.txt", "w") as f:
    f.write("\n".join(out))

log("")
log("=== Done ===")
