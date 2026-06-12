"""Test each source in a subprocess so one hang doesn't block others."""
import subprocess, sys

urls = [
    ('HN_API',      'https://hacker-news.firebaseio.com/v0/topstories.json'),
    ('Ars_Technica','https://feeds.arstechnica.com/arstechnica/index'),
    ('MIT_Tech_Rev','https://www.technologyreview.com/topic/artificial-intelligence/feed/'),
    ('TechCrunch',  'https://techcrunch.com/feed/'),
    ('Wired',       'https://www.wired.com/feed/rss'),
    ('Reddit',      'https://www.reddit.com/r/technology/hot/.json'),
    ('DeepSeek_API','https://api.deepseek.com/v1/models'),
]

for name, url in urls:
    code = (
        'import requests, time; t0=time.time();\n'
        'hdrs = {"User-Agent": "AI-News-Agent/1.0"};\n'
    )
    if 'reddit' in name.lower():
        code += 'hdrs["User-Agent"] = "AI-News-Agent/1.0 (by /u/news_agent_bot)";\n'
    code += (
        f'url = r"{url}";\n'
        'try:\n'
        '  r = requests.get(url, headers=hdrs, timeout=6);\n'
        '  ms = int((time.time()-t0)*1000);\n'
        '  print(f"OK {r.status_code} {ms}ms {len(r.content)}b");\n'
        'except Exception as e:\n'
        '  ms = int((time.time()-t0)*1000);\n'
        '  err = str(e)[:80].replace(chr(10)," ");\n'
        '  print(f"ERR {ms}ms {err}");\n'
    )
    try:
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout.strip().split('\n')[-1] if result.stdout.strip() else 'NO OUTPUT'
        print(f"[{name:15s}] {out}")
    except subprocess.TimeoutExpired:
        print(f"[{name:15s}] SUBPROCESS TIMEOUT (10s)")
    except Exception as e:
        print(f"[{name:15s}] SUBPROCESS ERROR: {e}")

print()
import socket
for domain in ['hacker-news.firebaseio.com','feeds.arstechnica.com',
               'www.technologyreview.com','techcrunch.com','www.wired.com',
               'www.reddit.com','api.deepseek.com']:
    try:
        ip = socket.getaddrinfo(domain, 443)[0][4][0]
        print(f"  DNS {domain:40s} -> {ip}")
    except Exception as e:
        print(f"  DNS {domain:40s} -> FAIL: {e}")
