from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from random import Random
from typing import Dict, Iterable, List

from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import session_scope
from .llm import get_llm_client
from .models import Article, Interaction
from .repository import (
    add_interaction,
    ingest_articles,
    list_by_category,
    list_by_nearby,
    list_by_score,
    list_by_search,
    list_by_source,
    trending_articles,
)


settings = get_settings()
_llm_client = get_llm_client()
_trending_cache: TTLCache[str, List[Article]] = TTLCache(maxsize=128, ttl=settings.trending_cache_ttl_seconds)


def load_data(file_path: str | Path = "data.json") -> None:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        articles = json.load(f)

    with session_scope() as session:
        ingest_articles(session, articles)
        _ensure_summaries(session, articles)
        _simulate_interactions(session, articles)


def _ensure_summaries(session: Session, articles: Iterable[dict]) -> None:
    for payload in articles:
        summary = _llm_client.summarize(payload["title"], payload["description"])
        session.query(Article).filter(Article.id == payload["id"]).update({"llm_summary": summary})


def _simulate_interactions(session: Session, articles: Iterable[dict]) -> None:
    existing = session.execute(select(Interaction.id).limit(1)).first()
    if existing:
        return
    seed = 42
    rng = Random(seed)
    now = datetime.utcnow()
    event_weights: Dict[str, float] = {"view": 1.0, "click": 1.5, "share": 2.5}
    for payload in articles:
        for _ in range(rng.randint(5, 20)):
            event_type = rng.choice(list(event_weights.keys()))
            weight = event_weights[event_type]
            jitter_minutes = rng.randint(0, 360)
            timestamp = now - timedelta(minutes=jitter_minutes)
            add_interaction(
                session,
                article_id=payload["id"],
                event_type=event_type,
                weight=weight,
                latitude=payload.get("latitude"),
                longitude=payload.get("longitude"),
                timestamp=timestamp,
            )


def _cache_key(lat: float, lon: float) -> str:
    precision = settings.trending_cluster_precision
    lat_bucket = round(lat / precision) * precision
    lon_bucket = round(lon / precision) * precision
    return f"{lat_bucket:.2f}:{lon_bucket:.2f}"


def get_articles_by_category(category: str, limit: int) -> List[Article]:
    with session_scope() as session:
        return list_by_category(session, category, limit)


def get_articles_by_source(source: str, limit: int) -> List[Article]:
    with session_scope() as session:
        return list_by_source(session, source, limit)


def get_articles_by_score(threshold: float, limit: int) -> List[Article]:
    with session_scope() as session:
        return list_by_score(session, threshold, limit)


def get_articles_by_search(query: str, limit: int) -> List[Article]:
    with session_scope() as session:
        return list_by_search(session, query, limit)


def get_articles_nearby(lat: float, lon: float, radius_km: float, limit: int) -> List[Article]:
    with session_scope() as session:
        return list_by_nearby(session, lat, lon, radius_km, limit)


def get_trending_articles(lat: float, lon: float, limit: int) -> List[Article]:
    key = _cache_key(lat, lon)
    if key in _trending_cache:
        return _trending_cache[key]
    with session_scope() as session:
        articles = trending_articles(session, lat, lon, limit)
        _trending_cache[key] = articles
        return articles


def resolve_query(intent: str, value: str | None, lat: float | None, lon: float | None, limit: int) -> List[Article]:
    if intent == "category" and value:
        return get_articles_by_category(value, limit)
    if intent == "source" and value:
        return get_articles_by_source(value, limit)
    if intent == "score" and value:
        try:
            threshold = float(value)
        except ValueError:
            threshold = 0.7
        return get_articles_by_score(threshold, limit)
    if intent == "nearby" and lat is not None and lon is not None:
        return get_articles_nearby(lat, lon, radius_km=10, limit=limit)
    if intent == "search":
        return get_articles_by_search(value or "", limit)
    return get_articles_by_search(value or "", limit)
