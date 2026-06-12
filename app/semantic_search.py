"""Semantic search with Chinese synonym mapping, entity recognition, and
cross-lingual search support.

Core capabilities:
- Chinese synonym mapping (e.g. 川普 → 特朗普 → Trump)
- Simplified/Traditional Chinese conversion
- Named entity recognition for person names, places, organizations
- Pinyin-based fuzzy matching
- Cross-lingual query expansion (Chinese ↔ English)
"""

import re
import json
import os
from typing import Set, List, Dict, Tuple, Optional
from dataclasses import dataclass, field


# ── Synonym Dictionary ────────────────────────────────────────────────────
# Format: { canonical_term: [synonym1, synonym2, ...] }

SYNONYM_DICT: Dict[str, List[str]] = {
    # Politics / World Leaders - Chinese variants
    "特朗普": ["川普", "donald trump", "trump", "donald j. trump", "唐纳德·特朗普"],
    "拜登": ["biden", "joe biden", "乔·拜登", "约瑟夫·拜登"],
    "习近平": ["xi jinping", "xi jinping", "习主席", "习近平主席", "xi"],
    "普京": ["putin", "vladimir putin", "弗拉基米尔·普京", "普丁"],
    "泽连斯基": ["zelensky", "zelenskyy", "volodymyr zelensky", "泽伦斯基"],
    "金正恩": ["kim jong un", "kim jong-un", "金正云"],
    "马克龙": ["macron", "emmanuel macron", "埃马纽埃尔·马克龙"],

    # Technology
    "人工智能": ["ai", "artificial intelligence", "artificial intelligent", "AI", "AI技术", "人工智能技术"],
    "机器学习": ["machine learning", "ml", "machinelearning"],
    "深度学习": ["deep learning", "dl", "deeplearning"],
    "自然语言处理": ["nlp", "natural language processing", "自然语言", "语言处理"],
    "大语言模型": ["llm", "large language model", "large language models", "大模型", "语言模型"],
    "神经网络": ["neural network", "neural networks", "神经网络模型"],
    "计算机视觉": ["computer vision", "cv", "机器视觉"],
    "机器人": ["robot", "robotics", "机器人技术"],
    "自动驾驶": ["self-driving", "autonomous driving", "无人驾驶", "autonomous vehicle"],
    "区块链": ["blockchain", "block chain", "分布式账本"],
    "元宇宙": ["metaverse", "web3", "虚拟世界"],
    "量子计算": ["quantum computing", "quantum", "量子计算机"],
    "5G": ["5g", "5th generation", "第五代移动通信"],

    # Industry / Companies
    "苹果": ["apple", "apple inc", "apple公司", "AAPL"],
    "谷歌": ["google", "alphabet", "Google"],
    "微软": ["microsoft", "msft", "微软公司", "microsoft corporation"],
    "亚马逊": ["amazon", "amzn", "aws"],
    "特斯拉": ["tesla", "tsla", "特斯拉汽车"],
    "Meta": ["meta", "facebook", "脸书", "fb"],
    "英伟达": ["nvidia", "nvda", "NVIDIA"],
    "华为": ["huawei", "华为技术", "华为公司"],
    "腾讯": ["tencent", "tencent holdings", "tcehy", "微信"],
    "阿里巴巴": ["alibaba", "baba", "alibaba group", "阿里"],
    "百度": ["baidu", "bidu"],
    "字节跳动": ["bytedance", "tiktok", "抖音", "字节"],
    "三星": ["samsung", "samsung electronics"],
    "台积电": ["tsmc", "台湾积体电路", "台湾积电"],

    # Science & Health
    "疫苗": ["vaccine", "vaccination", "接种"],
    "新冠": ["covid", "covid-19", "coronavirus", "冠状病毒", "sars-cov-2", "疫情"],
    "基因编辑": ["gene editing", "crispr", "基因工程"],
    "芯片": ["chip", "semiconductor", "处理器", "cpu", "gpu", "集成电路"],
    "电池": ["battery", "lithium-ion", "锂离子电池", "固态电池"],

    # Economy
    "通货膨胀": ["inflation", "通胀", "物价上涨"],
    "利率": ["interest rate", "加息", "降息"],
    "股市": ["stock market", "stock exchange", "股票市场", "shares"],
    "加密货币": ["cryptocurrency", "crypto", "比特币", "bitcoin", "以太坊", "ethereum"],

    # Climate & Environment
    "气候变化": ["climate change", "global warming", "全球变暖", "气候"],
    "可再生能源": ["renewable energy", "solar power", "wind power", "太阳能", "风能", "清洁能源"],
    "碳中和": ["carbon neutral", "net zero", "零排放", "carbon emission"],

    # International Relations
    "中美关系": ["china-us", "us-china", "sino-us", "中美贸易"],
    "俄乌战争": ["russia ukraine war", "ukraine war", "russian invasion", "俄乌冲突", "乌克兰"],
    "北约": ["nato", "北大西洋公约组织"],
    "欧盟": ["eu", "european union", "欧洲联盟"],
    "联合国": ["un", "united nations", "联合国组织"],

    # Internet / Social Media
    "社交媒体": ["social media", "social network", "twitter", "x", "instagram", "社交网络"],
    "数据隐私": ["data privacy", "privacy", "个人信息保护", "隐私"],
    "网络安全": ["cybersecurity", "cyber security", "网络攻击", "data breach", "黑客"],

    # Finance / Investment
    "首次公开募股": ["ipo", "首次公开募股", "上市", "initial public offering"],
    "风险投资": ["venture capital", "vc", "风投", "startup funding"],
    "对冲基金": ["hedge fund", "hedge funds"],
}


# ── Supplementary data ────────────────────────────────────────────────────

# Chinese characters that are commonly interchanged (Simplified ↔ Traditional)
SIMPLIFIED_TO_TRADITIONAL = {
    '对': '對', '发': '發', '关': '關', '时': '時', '说': '說',
    '话': '話', '过': '過', '这': '這', '为': '為', '国': '國',
    '会': '會', '经': '經', '门': '門', '开': '開', '东': '東',
    '长': '長', '间': '間', '问': '問', '认': '認', '识': '識',
}

TRADITIONAL_TO_SIMPLIFIED = {v: k for k, v in SIMPLIFIED_TO_TRADITIONAL.items()}

# Pinyin initial consonant mapping for fuzzy matching
PINYIN_INITIALS: Dict[str, str] = {
    'zh': 'z', 'z': 'zh',
    'ch': 'c', 'c': 'ch',
    'sh': 's', 's': 'sh',
    'an': 'ang', 'ang': 'an',
    'en': 'eng', 'eng': 'en',
    'in': 'ing', 'ing': 'in',
}

# ── Data structures ───────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """Result of a semantic search operation."""
    original_query: str
    expanded_terms: List[str] = field(default_factory=list)
    detected_entities: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({
            "original_query": self.original_query,
            "expanded_terms": self.expanded_terms,
            "detected_entities": self.detected_entities,
            "matched_terms": self.matched_terms,
        }, ensure_ascii=False)


# ── Core search functions ─────────────────────────────────────────────────

def expand_query(query: str) -> SearchResult:
    """Expand a search query with synonyms and related terms.

    Examples:
        "川普" → ["川普", "特朗普", "donald trump", "trump"]
        "AI" → ["ai", "artificial intelligence", "人工智能", "人工智能技术"]
    """
    result = SearchResult(original_query=query)
    expanded = set()
    detected = set()
    matched = set()

    query_lower = query.lower().strip()

    # Normalize whitespace
    search_terms = re.split(r'[\s,，、]+', query_lower)
    search_terms = [t for t in search_terms if t]

    for term in search_terms:
        if not term:
            continue
        # Check if term is in our synonym dictionary
        found_match = False
        for canonical, synonyms in SYNONYM_DICT.items():
            all_variants = [canonical.lower()] + [s.lower() for s in synonyms]

            # Check if our search term matches any variant
            if term in all_variants or any(term in v or v in term for v in all_variants):
                matched.add(canonical)
                expanded.add(canonical)
                for s in synonyms:
                    expanded.add(s)
                found_match = True

            # Check if any variant partially matches
            for variant in all_variants:
                if len(term) >= 2 and len(variant) >= 2:
                    if term in variant or variant in term:
                        matched.add(canonical)
                        expanded.add(canonical)
                        for s in synonyms:
                            expanded.add(s)
                        found_match = True

        if not found_match:
            expanded.add(term)

    # Also check if the full query matches any canonical term
    for canonical, synonyms in SYNONYM_DICT.items():
        if query_lower == canonical.lower():
            matched.add(canonical)
            expanded.add(canonical)
            for s in synonyms:
                expanded.add(s)
        for s in synonyms:
            if query_lower == s.lower():
                matched.add(canonical)
                expanded.add(canonical)
                for s2 in synonyms:
                    expanded.add(s2)

    # Detect named entities (uppercase English terms)
    entity_pattern = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
    for entity in entity_pattern:
        if entity.lower() not in {e.lower() for e in expanded}:
            detected.add(entity)

    # Add cross-lingual mappings for Chinese ↔ English
    # If query contains Chinese, add English equivalents
    if _has_chinese(query):
        _add_cross_lingual(expanded, query, target_lang="en")
    else:
        _add_cross_lingual(expanded, query, target_lang="zh")

    result.expanded_terms = list(expanded)
    result.detected_entities = list(detected)
    result.matched_terms = list(matched)
    return result


def _has_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', text))


def _add_cross_lingual(expanded: Set[str], query: str, target_lang: str):
    """Add cross-lingual translations for common terms."""
    for canonical, synonyms in SYNONYM_DICT.items():
        canonical_has_zh = _has_chinese(canonical)
        if target_lang == "en" and canonical_has_zh:
            # Chinese canonical → check if any synonym is English
            for s in synonyms:
                if not _has_chinese(s) and _query_similar(query, canonical):
                    expanded.add(s)
                    break
        elif target_lang == "zh" and not _has_chinese(canonical):
            # English canonical → check if query matches
            query_lower = query.lower()
            if query_lower == canonical.lower() or query_lower in [s.lower() for s in synonyms]:
                expanded.add(canonical)
                # Add Chinese synonyms too
                for s in synonyms:
                    if _has_chinese(s):
                        expanded.add(s)


def _query_similar(query: str, target: str) -> bool:
    """Check if query is similar to target using substring matching."""
    query_lower = query.lower().strip()
    target_lower = target.lower().strip()
    # Check if they share significant substrings
    min_len = min(len(query_lower), len(target_lower))
    if min_len <= 1:
        return False
    # Check overlap ratio
    overlap = len(set(query_lower) & set(target_lower))
    ratio = overlap / max(len(set(query_lower)), len(set(target_lower)), 1)
    return ratio > 0.3


def convert_chinese_script(text: str, to_simplified: bool = True) -> str:
    """Convert between Simplified and Traditional Chinese using zhconv."""
    try:
        import zhconv
        target = 'zh-cn' if to_simplified else 'zh-tw'
        return zhconv.convert(text, target)
    except ImportError:
        # Fallback to manual mapping if zhconv is not available
        mapping = TRADITIONAL_TO_SIMPLIFIED if to_simplified else SIMPLIFIED_TO_TRADITIONAL
        result = []
        for char in text:
            result.append(mapping.get(char, char))
        return ''.join(result)


def get_search_terms(query: str) -> List[str]:
    """Get expanded search terms suitable for querying news sources.

    This is the main API for integrating semantic search into the fetcher.
    Returns a list of query variations to try.
    """
    result = expand_query(query)

    # Build query variations
    variations = set()
    variations.add(query.strip())  # Original

    for term in result.expanded_terms:
        variations.add(term)

    # Add original query with common variations
    if _has_chinese(query):
        # Add Simplified/Traditional variants
        simplified = convert_chinese_script(query, to_simplified=True)
        if simplified != query:
            variations.add(simplified)
        traditional = convert_chinese_script(query, to_simplified=False)
        if traditional != query:
            variations.add(traditional)
        # Add English expanded terms
        for t in result.expanded_terms:
            if not _has_chinese(t):
                variations.add(t)
    else:
        # English query - add Chinese equivalents
        for t in result.expanded_terms:
            if _has_chinese(t):
                variations.add(t)

    # Sort: shorter terms first (more likely to match)
    sorted_variations = sorted(variations, key=len)

    # Deduplicate (case-insensitive)
    seen = set()
    final_terms = []
    for v in sorted_variations:
        key = v.lower().strip()
        if key and key not in seen and len(v) >= 1:
            seen.add(key)
            final_terms.append(v)

    return final_terms


def article_matches_query(article_text: str, query: str) -> bool:
    """Check if an article matches the expanded query.

    Returns True if the article content matches any expanded search term.
    """
    expanded = expand_query(query)
    text_lower = article_text.lower()

    for term in expanded.expanded_terms:
        if term.lower() in text_lower:
            return True
    return False


# ── Unit-testable examples ────────────────────────────────────────────────

def demo_search():
    """Demonstrate semantic search capabilities."""
    test_queries = [
        "川普",
        "AI",
        "人工智能",
        "比特币",
        "气候变化",
        "中美关系",
        "特斯拉",
    ]

    print("=" * 60)
    print("语义搜索演示")
    print("=" * 60)

    for query in test_queries:
        result = expand_query(query)
        terms = get_search_terms(query)
        print(f"\n查询: '{query}'")
        print(f"  展开词: {', '.join(result.expanded_terms[:8])}")
        print(f"  搜索词: {', '.join(terms[:5])}")
        print(f"  实体: {', '.join(result.detected_entities) if result.detected_entities else '无'}")

    # Test cross-lingual
    print("\n" + "=" * 60)
    print("跨语言搜索测试")
    print("=" * 60)
    for zh_query, en_query in [("机器学习", "machine learning"), ("疫苗", "vaccine")]:
        zh_terms = get_search_terms(zh_query)
        en_terms = get_search_terms(en_query)
        print(f"\n'{zh_query}' → 搜索词: {', '.join(zh_terms[:4])}")
        print(f"'{en_query}' → 搜索词: {', '.join(en_terms[:4])}")


if __name__ == "__main__":
    demo_search()
