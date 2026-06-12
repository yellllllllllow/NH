"""News fetching module with proxy support and timeout handling."""

import requests
from typing import List, Dict, Optional


NEWS_API_URL = "https://newsapi.org/v2/everything"

# Fallback RSS-based news sources (no API key needed)
RSS_FALLBACK_SOURCES = [
    {
        "title": "MIT Technology Review - AI",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/"
    },
    {
        "title": "Ars Technica - AI",
        "url": "https://feeds.arstechnica.com/arstechnica/index"
    },
]


def fetch_news(api_key: str, query: str = "Artificial Intelligence",
               page_size: int = 10, proxies: dict = None,
               timeout: int = 10) -> Optional[List[Dict]]:
    """Fetch news from newsapi.org via REST API.

    Returns list of article dicts, or None if API key is missing,
    or empty list on failure.
    """
    if not api_key:
        return None

    params = {
        "q": query,
        "apiKey": api_key,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": page_size
    }

    try:
        response = requests.get(
            NEWS_API_URL, params=params,
            proxies=proxies, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            return []

        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title", "Untitled"),
                "source": article.get("source", {}).get("name", "Unknown"),
                "summary": (
                    article.get("description") or
                    article.get("content") or
                    "No content available."
                ),
                "url": article.get("url", ""),
                "published": article.get("publishedAt", ""),
            })
        return articles

    except requests.Timeout:
        raise ConnectionError("请求超时：无法连接到新闻源，请检查网络或代理设置。")
    except requests.ConnectionError as e:
        raise ConnectionError(f"网络连接失败：{str(e)[:100]}")
    except requests.HTTPError as e:
        if response.status_code == 401:
            raise PermissionError("API Key 无效，请在设置中配置正确的 API Key。")
        raise RuntimeError(f"HTTP 错误 {response.status_code}")
    except requests.RequestException as e:
        raise RuntimeError(f"请求失败：{str(e)[:100]}")


def validate_api_key(api_key: str, proxies: dict = None,
                     timeout: int = 10) -> Dict:
    """Validate a NewsAPI key by making a minimal test request.

    Returns dict with 'valid' bool and 'message' str.
    """
    if not api_key:
        return {"valid": False, "message": "API Key 为空"}

    params = {"q": "test", "apiKey": api_key, "pageSize": 1}
    try:
        resp = requests.get(
            NEWS_API_URL, params=params,
            proxies=proxies, timeout=timeout
        )
        if resp.status_code == 200:
            return {"valid": True, "message": "API Key 有效"}
        elif resp.status_code == 401:
            return {"valid": False, "message": "API Key 无效或被拒绝"}
        else:
            return {"valid": False, "message": f"HTTP {resp.status_code}"}
    except requests.Timeout:
        return {"valid": False, "message": "连接超时"}
    except requests.ConnectionError:
        return {"valid": False, "message": "网络连接失败"}
    except Exception as e:
        return {"valid": False, "message": str(e)[:100]}
