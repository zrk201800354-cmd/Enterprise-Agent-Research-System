from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from quant_agent.news.finnhub import NewsItem

# Common English stop words
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "must",
    "it", "its", "this", "that", "these", "those", "i", "we", "you",
    "he", "she", "they", "me", "us", "him", "her", "them", "my", "our",
    "your", "his", "their", "what", "which", "who", "whom", "how", "when",
    "where", "why", "not", "no", "nor", "so", "up", "out", "if", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "same", "than", "too", "very", "just", "over", "only",
    "also", "more", "most", "other", "some", "such", "here", "there",
    "all", "each", "every", "both", "few", "many", "much", "any", "new",
    "now", "then", "once", "says", "said", "report", "reports",
})

# Sentiment keywords
_POSITIVE_WORDS = frozenset({
    "surge", "rally", "gain", "rise", "jump", "soar", "high", "record",
    "profit", "growth", "bull", "bullish", "upgrade", "beat", "beats",
    "strong", "positive", "optimism", "optimistic", "recovery", "boom",
    "buy", "outperform", "breakthrough", "success", "win", "boost",
    "up", "higher", "raises", "raised", "improve", "improved", "gain",
    "gains", "rises", "surges", "jumps", "soars", "climbs", "advances",
    "tops", "hits", "reaches", "exceeds", "strength", "momentum",
})

_NEGATIVE_WORDS = frozenset({
    "fall", "drop", "decline", "crash", "plunge", "sink", "low", "loss",
    "losses", "bear", "bearish", "downgrade", "miss", "misses", "weak",
    "negative", "fear", "fearful", "recession", "crisis", "sell", "selloff",
    "underperform", "fail", "failure", "risk", "risks", "warning", "warn",
    "down", "lower", "cuts", "cut", "reduce", "reduced", "concern",
    "concerns", "worries", "worried", "slump", "tumble", "tumbles",
    "falls", "drops", "declines", "crashes", "plunges", "sinks",
    "threat", "threatens", "pressure", "pressed", "volatility",
})


@dataclass(frozen=True)
class SourceStats:
    name: str
    count: int


@dataclass(frozen=True)
class KeywordStat:
    word: str
    count: int


@dataclass(frozen=True)
class NewsSummary:
    total_articles: int
    sentiment: str  # "positive", "negative", "neutral"
    sentiment_score: float  # -1.0 to 1.0
    positive_count: int
    negative_count: int
    neutral_count: int
    top_sources: list[SourceStats]
    top_keywords: list[KeywordStat]
    summary_text: str


def _extract_keywords(headlines: list[str], top_n: int = 15) -> list[KeywordStat]:
    """Extract top keywords from headlines by frequency."""
    word_counts: Counter[str] = Counter()
    for headline in headlines:
        words = re.findall(r"[a-zA-Z]{3,}", headline.lower())
        for word in words:
            if word not in _STOP_WORDS and len(word) >= 3:
                word_counts[word] += 1
    return [KeywordStat(word=w, count=c) for w, c in word_counts.most_common(top_n)]


def _analyze_sentiment(headlines: list[str]) -> tuple[str, float, int, int, int]:
    """Analyze overall sentiment from headlines. Returns (label, score, pos, neg, neu)."""
    positive = 0
    negative = 0
    for headline in headlines:
        words = set(re.findall(r"[a-zA-Z]+", headline.lower()))
        pos_hits = len(words & _POSITIVE_WORDS)
        neg_hits = len(words & _NEGATIVE_WORDS)
        if pos_hits > neg_hits:
            positive += 1
        elif neg_hits > pos_hits:
            negative += 1

    total = len(headlines) or 1
    score = (positive - negative) / total
    neutral = len(headlines) - positive - negative

    if score > 0.1:
        label = "positive"
    elif score < -0.1:
        label = "negative"
    else:
        label = "neutral"
    return label, round(score, 3), positive, negative, neutral


def _build_summary_text(
    sentiment: str,
    top_sources: list[SourceStats],
    top_keywords: list[KeywordStat],
    total: int,
    pos: int,
    neg: int,
) -> str:
    """Generate a brief human-readable summary."""
    parts = []

    # Sentiment
    if sentiment == "positive":
        parts.append(f"市场情绪偏积极，共 {total} 条资讯中 {pos} 条为正面。")
    elif sentiment == "negative":
        parts.append(f"市场情绪偏消极，共 {total} 条资讯中 {neg} 条为负面。")
    else:
        parts.append(f"市场情绪中性，共 {total} 条资讯。")

    # Top sources
    if top_sources:
        src_str = "、".join(f"{s.name}({s.count})" for s in top_sources[:3])
        parts.append(f"主要来源：{src_str}。")

    # Top keywords
    if top_keywords:
        kw_str = "、".join(kw.word.upper() for kw in top_keywords[:5])
        parts.append(f"热点关键词：{kw_str}。")

    return "".join(parts)


def summarize_news(items: list[NewsItem]) -> NewsSummary:
    """Analyze a list of news items and produce a structured summary."""
    if not items:
        return NewsSummary(
            total_articles=0,
            sentiment="neutral",
            sentiment_score=0.0,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            top_sources=[],
            top_keywords=[],
            summary_text="暂无新闻数据。",
        )

    headlines = [item.headline for item in items if item.headline]

    # Source grouping
    source_counts: Counter[str] = Counter()
    for item in items:
        if item.source:
            source_counts[item.source] += 1
    top_sources = [SourceStats(name=s, count=c) for s, c in source_counts.most_common(10)]

    # Keywords
    top_keywords = _extract_keywords(headlines)

    # Sentiment
    sentiment, score, pos, neg, neu = _analyze_sentiment(headlines)

    # Summary text
    summary_text = _build_summary_text(sentiment, top_sources, top_keywords, len(items), pos, neg)

    return NewsSummary(
        total_articles=len(items),
        sentiment=sentiment,
        sentiment_score=score,
        positive_count=pos,
        negative_count=neg,
        neutral_count=neu,
        top_sources=top_sources,
        top_keywords=top_keywords,
        summary_text=summary_text,
    )
