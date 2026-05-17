from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import urllib.request
import json


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    url: str
    summary: str
    datetime: str
    image: str | None = None


class FinnhubClient:
    BASE_URL = "https://finnhub.io/api/v1"
    CACHE_TTL = 900  # 15 minutes

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")
        self._cache: dict[str, tuple[float, list[NewsItem]]] = {}

    def _get(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        sep = "&" if "?" in endpoint else "?"
        query = sep + "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url += query
        token_param = f"token={self.api_key}"
        url += f"&{token_param}" if "?" in url else f"?{token_param}"

        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _cached_get(self, cache_key: str, endpoint: str, params: dict[str, str] | None = None) -> list[NewsItem]:
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if now - cached_time < self.CACHE_TTL:
                return cached_data

        raw = self._get(endpoint, params)
        items = [
            NewsItem(
                headline=item.get("headline", ""),
                source=item.get("source", ""),
                url=item.get("url", ""),
                summary=item.get("summary", ""),
                datetime=datetime.fromtimestamp(item.get("datetime", 0)).isoformat() if item.get("datetime") else "",
                image=item.get("image"),
            )
            for item in (raw if isinstance(raw, list) else [])
        ]
        self._cache[cache_key] = (now, items)
        return items

    def fetch_market_news(self, category: str = "general") -> list[NewsItem]:
        cache_key = f"market_{category}"
        return self._cached_get(cache_key, "/news", {"category": category})

    def fetch_company_news(self, symbol: str, days_back: int = 7) -> list[NewsItem]:
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        cache_key = f"company_{symbol}_{from_date}_{to_date}"
        return self._cached_get(
            cache_key,
            "/company-news",
            {"symbol": symbol, "from": from_date, "to": to_date},
        )
