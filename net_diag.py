"""Diagnose news source connectivity."""
import socket, requests, time, sys

socket.setdefaulttimeout(10)
s = requests.Session()
results = []

urls = [
    ('HN_API',      'https://hacker-news.firebaseio.com/v0/topstories.json'),
    ('Ars_Technica','https://feeds.arstechnica.com/arstechnica/index'),
    ('MIT_Tech_Rev','https://www.technologyreview.com/topic/artificial-intelligence/feed/'),
    ('TechCrunch',  'https://techcrunch.com/feed/'),
    ('Wired',       'https://www.wired.com/feed/rss'),
    ('Reddit',      'https://www.reddit.com/r/technology/hot/.json'),
    ('DeepSeek_API','https://api.deepseek.com/v1/models'),
]

print("=" * 60)
print("News Source Connectivity Diagnostics")
print("=" * 60)

for name, url in urls:
    t0 = time.time()
    try:
        hdrs = {'User-Agent': 'AI-News-Agent/1.0'}
        if 'reddit' in name.lower():
            hdrs['User-Agent'] = 'AI-News-Agent/1.0 (by /u/news_agent_bot)'
        r = s.get(url, headers=hdrs, timeout=10)
        ms = int((time.time()-t0)*1000)
        status = f"HTTP {r.status_code}  {ms}ms  ({len(r.content)} bytes)"
        print(f"  [OK] {name:15s} | {status}")
    except requests.Timeout:
        ms = int((time.time()-t0)*1000)
        print(f"  [!!] {name:15s} | TIMEOUT after {ms}ms")
    except requests.ConnectionError as e:
        ms = int((time.time()-t0)*1000)
        err = str(e)[:80]
        print(f"  [!!] {name:15s} | CONN FAIL ({ms}ms): {err}")
    except Exception as e:
        ms = int((time.time()-t0)*1000)
        print(f"  [!!] {name:15s} | ERROR ({ms}ms): {str(e)[:80]}")

print()
print("=" * 60)
print("DNS Resolution Check")
print("=" * 60)
domains = ['hacker-news.firebaseio.com','feeds.arstechnica.com',
           'www.technologyreview.com','techcrunch.com','www.wired.com',
           'www.reddit.com','newsapi.org','api.deepseek.com']
for d in domains:
    try:
        ip = socket.getaddrinfo(d, 443)[0][4][0]
        print(f"  {d:40s} -> {ip}")
    except Exception as e:
        print(f"  {d:40s} -> FAIL: {str(e)[:40]}")

print()
print("=" * 60)
print("Proxy Environment")
print("=" * 60)
import os
for var in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:
    val = os.environ.get(var,'')
    print(f"  {var:15s} = {'(set)' if val else '(unset)'}")
    if val:
        print(f"  {'':15s}   {val}")

print()
print("=== Diagnostics Complete ===")
