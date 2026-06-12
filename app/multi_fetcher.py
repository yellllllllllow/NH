"""Multi-source news fetcher with automatic fallback mechanism.

Supports multiple source types:
- REST API (NewsAPI, Hacker News, Reddit)
- RSS/Atom feeds (MIT Tech Review, Ars Technica, BBC, Reuters)
- Automatic fallback when primary source is unavailable
"""

import os
import socket
import requests
import xml.etree.ElementTree as ET
import html
import re
import time
from typing import List, Dict, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field

# Global socket timeout to prevent hangs on DNS / slow connections
socket.setdefaulttimeout(10)


def detect_proxies() -> dict:
    """Detect system proxy settings for requests library.

    ONLY uses environment variables (HTTP_PROXY, HTTPS_PROXY).
    Port scanning is NOT performed — it is unreliable because:
    - Common proxy ports (10808, 7890) may use SOCKS5 protocol
      which is incompatible with requests' HTTP proxy mechanism.
    - Scanning adds latency for every fetch operation.
    - Environment variables are the standard, reliable mechanism.

    Returns a dict suitable for requests.get(proxies=...).
    """
    proxies = {}

    for var in ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"]:
        val = os.environ.get(var, "").strip()
        if val:
            proxies["https"] = val
            proxies["http"] = val
            return proxies

    return proxies


from .news_sources import (
    NewsSource, SourceType, SourceStatus,
    load_sources, get_source_by_id,
)


# ── Article model ──────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    """Result of fetching from a single source."""
    source_id: str
    source_name: str
    articles: List[Dict] = field(default_factory=list)
    success: bool = False
    error_message: str = ""
    elapsed_ms: int = 0
    status_code: Optional[int] = None
    cached: bool = False


# ── Individual source fetchers ────────────────────────────────────────────

def _fetch_newsapi(source: NewsSource, query: str, page_size: int,
                   api_key: str, proxies: dict, timeout: int) -> FetchResult:
    """Fetch from NewsAPI.org REST API."""
    start = datetime.now()
    try:
        params = {
            "q": query,
            "apiKey": api_key or source.api_key,
            "sortBy": "publishedAt",
            "pageSize": page_size,
        }
        # Language filter based on query content
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in query)
        params["language"] = "zh" if has_chinese else "en"

        resp = requests.get(
            source.url, params=params, proxies=proxies, timeout=timeout
        )
        elapsed = int((datetime.now() - start).total_seconds() * 1000)

        if resp.status_code != 200:
            return FetchResult(
                source_id=source.id, source_name=source.name,
                success=False, error_message=f"HTTP {resp.status_code}",
                elapsed_ms=elapsed, status_code=resp.status_code,
            )

        data = resp.json()
        if data.get("status") != "ok":
            return FetchResult(
                source_id=source.id, source_name=source.name,
                success=False, error_message=data.get("message", "Unknown error"),
                elapsed_ms=elapsed,
            )

        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title", "Untitled"),
                "source": source.name,
                "source_id": source.id,
                "summary": (
                    article.get("description")
                    or article.get("content")
                    or "No content available."
                )[:500],
                "url": article.get("url", ""),
                "published": article.get("publishedAt", ""),
                "author": article.get("author", ""),
                "image_url": article.get("urlToImage", ""),
            })

        return FetchResult(
            source_id=source.id, source_name=source.name,
            articles=articles, success=True, elapsed_ms=elapsed,
        )

    except requests.Timeout:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message="请求超时", elapsed_ms=timeout * 1000,
        )
    except requests.ConnectionError as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=f"连接失败: {str(e)[:80]}",
        )
    except Exception as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=str(e)[:100],
        )


def _fetch_rss(source: NewsSource, query: str, page_size: int,
               proxies: dict, timeout: int) -> FetchResult:
    """Fetch news from an RSS/Atom feed."""
    start = datetime.now()
    feed_url = source.rss_feed_url or source.url
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        headers.update(source.custom_headers)

        resp = requests.get(feed_url, headers=headers, proxies=proxies, timeout=timeout)
        elapsed = int((datetime.now() - start).total_seconds() * 1000)

        if resp.status_code != 200:
            return FetchResult(
                source_id=source.id, source_name=source.name,
                success=False, error_message=f"HTTP {resp.status_code}",
                elapsed_ms=elapsed, status_code=resp.status_code,
            )

        articles = _parse_rss_feed(resp.text, source, query)
        # Limit to page_size
        articles = articles[:page_size]

        return FetchResult(
            source_id=source.id, source_name=source.name,
            articles=articles, success=True, elapsed_ms=elapsed,
        )

    except requests.Timeout:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message="请求超时", elapsed_ms=timeout * 1000,
        )
    except requests.ConnectionError as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=f"连接失败: {str(e)[:80]}",
        )
    except ET.ParseError as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=f"XML解析错误: {str(e)[:80]}",
        )
    except Exception as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=str(e)[:100],
        )


def _parse_rss_feed(xml_content: str, source: NewsSource, query: str) -> List[Dict]:
    """Parse RSS/Atom XML content into article dicts."""
    articles = []
    root = ET.fromstring(xml_content)

    # Determine if RSS 2.0 or Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    is_atom = root.find(".//atom:entry", ns) is not None

    if is_atom:
        # Atom format
        entries = root.findall(".//atom:entry", ns)
        for entry in entries:
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            summary_el = entry.find("atom:summary", ns) or entry.find("atom:content", ns)
            published_el = entry.find("atom:published", ns) or entry.find("atom:updated", ns)

            title = _get_text(title_el)
            url = link_el.get("href", "") if link_el is not None else ""
            summary = _get_text(summary_el) or ""
            published = _get_text(published_el) or ""

            if title and _matches_query(title + summary, query):
                articles.append({
                    "title": html.unescape(title.strip()),
                    "source": source.name,
                    "source_id": source.id,
                    "summary": html.unescape(summary.strip())[:500],
                    "url": url,
                    "published": published,
                    "author": "",
                    "image_url": "",
                })
    else:
        # RSS 2.0 format
        items = root.findall(".//item")
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_date_el = item.find("pubDate")

            title = _get_text(title_el)
            url = _get_text(link_el) or ""
            summary = _get_text(desc_el) or ""
            published = _get_text(pub_date_el) or ""

            if title and _matches_query(title + summary, query):
                articles.append({
                    "title": html.unescape(title.strip()),
                    "source": source.name,
                    "source_id": source.id,
                    "summary": html.unescape(
                        re.sub(r'<[^>]+>', '', summary).strip()
                    )[:500],
                    "url": url,
                    "published": published,
                    "author": "",
                    "image_url": "",
                })

    return articles


def _fetch_hackernews(source: NewsSource, query: str, page_size: int,
                      api_key: str, proxies: dict, timeout: int) -> FetchResult:
    """Fetch from Hacker News Firebase API."""
    start = datetime.now()
    try:
        # Get top story IDs
        resp = requests.get(
            f"{source.url}/topstories.json",
            proxies=proxies, timeout=timeout
        )
        elapsed = int((datetime.now() - start).total_seconds() * 1000)

        if resp.status_code != 200:
            return FetchResult(
                source_id=source.id, source_name=source.name,
                success=False, error_message=f"HTTP {resp.status_code}",
                elapsed_ms=elapsed, status_code=resp.status_code,
            )

        story_ids = resp.json()[:page_size * 2]  # Fetch extra for filtering

        articles = []
        for story_id in story_ids:
            if len(articles) >= page_size:
                break
            try:
                story_resp = requests.get(
                    f"{source.url}/item/{story_id}.json",
                    proxies=proxies, timeout=5  # Per-item timeout: HN items should be fast
                )
                if story_resp.status_code == 200:
                    story = story_resp.json()
                    if story and story.get("title"):
                        title = story.get("title", "")
                        url = story.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                        text = story.get("text", "")
                        if _matches_query(title + text, query):
                            articles.append({
                                "title": title,
                                "source": source.name,
                                "source_id": source.id,
                                "summary": (text or "")[:300],
                                "url": url,
                                "published": datetime.fromtimestamp(
                                    story.get("time", 0)
                                ).isoformat() if story.get("time") else "",
                                "author": story.get("by", ""),
                                "image_url": "",
                            })
            except Exception:
                continue

        return FetchResult(
            source_id=source.id, source_name=source.name,
            articles=articles, success=len(articles) > 0,
            error_message="" if articles else "未匹配到相关文章",
            elapsed_ms=elapsed,
        )

    except requests.Timeout:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message="请求超时", elapsed_ms=timeout * 1000,
        )
    except Exception as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=str(e)[:100],
        )


def _fetch_reddit(source: NewsSource, query: str, page_size: int,
                  api_key: str, proxies: dict, timeout: int) -> FetchResult:
    """Fetch from Reddit public JSON API."""
    start = datetime.now()
    try:
        # Reddit requires a descriptive User-Agent and rate limiting
        headers = {
            "User-Agent": "AI-News-Agent/1.0 (by /u/news_agent_bot)",
            "Accept": "application/json",
        }
        headers.update(source.custom_headers)

        # Use a shorter timeout for Reddit - it's known to be rate-limited
        reddit_timeout = min(timeout, 8)

        resp = requests.get(
            source.url, headers=headers, proxies=proxies, timeout=reddit_timeout
        )
        elapsed = int((datetime.now() - start).total_seconds() * 1000)

        if resp.status_code == 429:
            return FetchResult(
                source_id=source.id, source_name=source.name,
                success=False,
                error_message="Reddit 请求频率限制 (HTTP 429)，请稍后再试",
                elapsed_ms=elapsed, status_code=429,
            )
        if resp.status_code != 200:
            return FetchResult(
                source_id=source.id, source_name=source.name,
                success=False, error_message=f"HTTP {resp.status_code}",
                elapsed_ms=elapsed, status_code=resp.status_code,
            )

        data = resp.json()
        articles = []
        children = data.get("data", {}).get("children", [])
        for child in children[:page_size]:
            post = child.get("data", {})
            title = post.get("title", "")
            url = post.get("url", "")
            text = post.get("selftext", "")
            if _matches_query(title + text, query):
                articles.append({
                    "title": title,
                    "source": source.name,
                    "source_id": source.id,
                    "summary": (text or "")[:500],
                    "url": url,
                    "published": datetime.fromtimestamp(
                        post.get("created_utc", 0)
                    ).isoformat() if post.get("created_utc") else "",
                    "author": post.get("author", ""),
                    "image_url": post.get("thumbnail", "") if post.get("thumbnail", "").startswith("http") else "",
                })

        return FetchResult(
            source_id=source.id, source_name=source.name,
            articles=articles, success=True, elapsed_ms=elapsed,
        )

    except requests.Timeout:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message="请求超时", elapsed_ms=timeout * 1000,
        )
    except Exception as e:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message=str(e)[:100],
        )


# ── Helper functions ──────────────────────────────────────────────────────

def _get_text(element) -> str:
    """Safely get text from an XML element."""
    if element is None:
        return ""
    return (element.text or "").strip()


def _matches_query(text: str, query: str) -> bool:
    """Check if text matches the search query (case-insensitive)."""
    if not query:
        return True
    query_lower = query.lower()
    text_lower = text.lower()
    # Split query into words and check if any match
    query_words = query_lower.split()
    return any(word in text_lower for word in query_words)


# ── Source type dispatcher ────────────────────────────────────────────────

_SOURCE_FETCHERS = {
    "newsapi": _fetch_newsapi,
    "hacker_news": _fetch_hackernews,
    "reddit": _fetch_reddit,
}

# Sources that use RSS fetcher
_RSS_SOURCE_IDS = {"mit_tech_review", "ars_technica", "techcrunch", "wired"}


def fetch_from_source(source: NewsSource, query: str,
                      page_size: int = 10,
                      api_key: str = "",
                      proxies: dict = None) -> FetchResult:
    """Fetch news from a specific source based on its type and ID."""
    # Auto-detect proxy if not explicitly provided
    if proxies is None:
        proxies = detect_proxies()
    timeout = source.timeout

    # Skip NewsAPI if no API key is configured
    if source.id == "newsapi" and not api_key and not source.api_key:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False, error_message="NewsAPI 需要单独的 API Key（非 DeepSeek Key），请在新闻源管理中配置。",
        )

    if source.id in _SOURCE_FETCHERS:
        return _SOURCE_FETCHERS[source.id](
            source, query, page_size, api_key, proxies, timeout
        )
    elif source.type == SourceType.RSS or source.id in _RSS_SOURCE_IDS:
        return _fetch_rss(source, query, page_size, proxies, timeout)
    elif source.type == SourceType.API:
        # Generic API fetch - try to use as RSS if no dedicated handler
        return _fetch_rss(source, query, page_size, proxies, timeout)
    else:
        return FetchResult(
            source_id=source.id, source_name=source.name,
            success=False,
            error_message=f"不支持的源类型: {source.type.value}",
        )


def test_source_connection(source: NewsSource, api_key: str = "",
                           proxies: dict = None) -> FetchResult:
    """Test connection to a source (fetches 1 article)."""
    return fetch_from_source(source, query="test", page_size=1,
                             api_key=api_key, proxies=proxies)


# ── Multi-source fetch with fallback ──────────────────────────────────────

def fetch_with_fallback(
    query: str,
    page_size: int = 10,
    primary_source_id: Optional[str] = None,
    api_key: str = "",
    proxies: dict = None,
    sources: Optional[List[NewsSource]] = None,
    progress_callback: Optional[Callable[[str, bool], None]] = None,
) -> tuple:
    """Fetch news with automatic fallback.

    Tries sources in fallback order until enough articles are collected.
    Returns (articles: List[Dict], results: List[FetchResult]).
    """
    if sources is None:
        sources = load_sources()

    # Sort by fallback_order
    sorted_sources = sorted(
        [s for s in sources if s.enabled],
        key=lambda s: s.fallback_order,
    )

    # Move primary source to front if specified
    if primary_source_id:
        primary = get_source_by_id(sources, primary_source_id)
        if primary and primary in sorted_sources:
            sorted_sources.remove(primary)
            sorted_sources.insert(0, primary)

    all_articles = []
    all_results = []
    seen_urls = set()
    errors = []

    for source in sorted_sources:
        if len(all_articles) >= page_size:
            break

        if progress_callback:
            progress_callback(f"正在从 {source.name} 获取...", False)

        result = fetch_from_source(
            source, query,
            page_size=page_size - len(all_articles),
            api_key=api_key,
            proxies=proxies,
        )
        all_results.append(result)

        if result.success and result.articles:
            # Deduplicate by URL
            new_count = 0
            for article in result.articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(article)
                    new_count += 1

            if progress_callback:
                status_str = f"{source.name}: 获取到 {new_count} 条"
                progress_callback(status_str, True)
        else:
            err = f"{source.name}: {result.error_message}"
            errors.append(err)
            if progress_callback:
                progress_callback(f"{source.name}: 不可用 - {result.error_message}", False)

    return all_articles, all_results
