"""News source definitions, models, and configuration persistence.

Supports:
- Built-in sources (NewsAPI, RSS feeds, public APIs)
- Custom user-defined sources
- Source status tracking (online/offline)
- Persistence via JSON file
"""

import json
import os
import sys
import re
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class SourceType(Enum):
    API = "api"          # REST API (e.g. NewsAPI)
    RSS = "rss"          # RSS/Atom feed
    WEB = "web"          # Web scraping


class SourceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class NewsSource:
    """Represents a single news source configuration."""
    id: str
    name: str
    type: SourceType
    url: str
    enabled: bool = True
    requires_api_key: bool = False
    api_key: str = ""
    rss_feed_url: str = ""
    status: SourceStatus = SourceStatus.UNKNOWN
    last_checked: float = 0.0
    fallback_order: int = 99
    description: str = ""
    language: str = "en"
    custom_headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 10  # 每个源的请求超时时间（秒）

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NewsSource":
        d["type"] = SourceType(d.get("type", "api"))
        d["status"] = SourceStatus(d.get("status", "unknown"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Built-in source definitions ──────────────────────────────────────────

# NewsAPI.org - primary, requires API key
SRC_NEWSAPI = NewsSource(
    id="newsapi",
    name="NewsAPI.org",
    type=SourceType.API,
    url="https://newsapi.org/v2/everything",
    requires_api_key=True,
    fallback_order=10,
    enabled=False,
    description="Comprehensive news aggregator with global coverage. Requires free API key from newsapi.org. Disabled by default: requires a separate NewsAPI key.",
    language="en",
)

# MIT Technology Review - free RSS
SRC_MIT_TECH_REVIEW = NewsSource(
    id="mit_tech_review",
    name="MIT Technology Review",
    type=SourceType.RSS,
    url="https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    rss_feed_url="https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    fallback_order=2,
    description="Leading technology magazine covering AI, computing, and innovation.",
    language="en",
)

# Ars Technica - free RSS
SRC_ARS_TECHNICA = NewsSource(
    id="ars_technica",
    name="Ars Technica",
    type=SourceType.RSS,
    url="https://feeds.arstechnica.com/arstechnica/index",
    rss_feed_url="https://feeds.arstechnica.com/arstechnica/index",
    fallback_order=3,
    description="Technology news, analysis, and reviews with in-depth coverage.",
    language="en",
)

# TechCrunch - free RSS (accessible from China)
SRC_TECHCRUNCH = NewsSource(
    id="techcrunch",
    name="TechCrunch",
    type=SourceType.RSS,
    url="https://techcrunch.com/feed/",
    rss_feed_url="https://techcrunch.com/feed/",
    fallback_order=4,
    description="Leading technology media covering startups, innovation, and tech news.",
    language="en",
)

# Hacker News - free API
SRC_HACKER_NEWS = NewsSource(
    id="hacker_news",
    name="Hacker News",
    type=SourceType.API,
    url="https://hacker-news.firebaseio.com/v0",
    fallback_order=5,
    description="Social news website focusing on computer science and entrepreneurship. No API key required.",
    language="en",
)

# Reddit - free public JSON API
SRC_REDDIT = NewsSource(
    id="reddit",
    name="Reddit (r/technology)",
    type=SourceType.API,
    url="https://www.reddit.com/r/technology/hot/.json",
    fallback_order=6,
    description="Reddit technology community discussions and news links.",
    language="en",
    custom_headers={"User-Agent": "AI-News-Agent/1.0"},
)

# Wired - free RSS (accessible from China)
SRC_WIRED = NewsSource(
    id="wired",
    name="Wired",
    type=SourceType.RSS,
    url="https://www.wired.com/feed/rss",
    rss_feed_url="https://www.wired.com/feed/rss",
    fallback_order=7,
    description="In-depth technology and science coverage from Wired magazine.",
    language="en",
)

# Default list of built-in sources
BUILT_IN_SOURCES = [
    SRC_NEWSAPI,
    SRC_MIT_TECH_REVIEW,
    SRC_ARS_TECHNICA,
    SRC_TECHCRUNCH,
    SRC_HACKER_NEWS,
    SRC_REDDIT,
    SRC_WIRED,
]


# ── Configuration persistence ────────────────────────────────────────────

SOURCES_CONFIG_FILE = "news_sources.json"


def get_sources_config_path() -> str:
    """Get the news sources config file path based on runtime context."""
    if hasattr(sys, 'frozen'):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, SOURCES_CONFIG_FILE)


def load_sources() -> List[NewsSource]:
    """Load sources from config file, merging with built-in defaults."""
    sources_map: Dict[str, NewsSource] = {}
    for s in BUILT_IN_SOURCES:
        sources_map[s.id] = s

    path = get_sources_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    try:
                        src = NewsSource.from_dict(item)
                        if src.id:
                            sources_map[src.id] = src
                    except Exception:
                        continue
            elif isinstance(data, dict):
                # Support dict format for backward compatibility
                for src_id, item in data.items():
                    item["id"] = src_id
                    try:
                        src = NewsSource.from_dict(item)
                        sources_map[src_id] = src
                    except Exception:
                        continue
        except (json.JSONDecodeError, OSError):
            pass

    return list(sources_map.values())


def save_sources(sources: List[NewsSource]) -> bool:
    """Save sources to config file."""
    path = get_sources_config_path()
    try:
        data = [s.to_dict() for s in sources]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def get_source_by_id(sources: List[NewsSource], src_id: str) -> Optional[NewsSource]:
    """Find a source by its ID."""
    for s in sources:
        if s.id == src_id:
            return s
    return None


def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'([\w\-]+\.)+[\w\-]+'  # domain
        r'(:\d+)?'  # optional port
        r'(/[\w\-\.~:/?#\[\]@!$&\'()*+,;=%]*)?'  # path
        r'$',
        re.IGNORECASE
    )
    return bool(pattern.match(url))


def is_valid_rss_url(url: str) -> bool:
    """Check if URL looks like an RSS feed."""
    url_lower = url.lower()
    rss_indicators = ['rss', 'feed', 'atom', 'xml']
    return any(indicator in url_lower for indicator in rss_indicators) or url_lower.endswith('.xml')


def generate_source_id(name: str) -> str:
    """Generate a unique source ID from a name."""
    base = re.sub(r'[^a-zA-Z0-9\s\-_]', '', name.lower())
    base = re.sub(r'\s+', '_', base.strip())
    return base or f"custom_{int(time.time())}"
