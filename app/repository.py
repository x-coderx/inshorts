from __future__ import annotations

from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from typing import List, Optional, Sequence

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from .models import Article, Interaction


def ingest_articles(session: Session, articles: Sequence[dict]) -> None:
    existing_ids = {row[0] for row in session.execute(select(Article.id)).all()}
    for payload in articles:
        if payload["id"] in existing_ids:
            continue
        article = Article(
            id=payload["id"],
            title=payload["title"],
            description=payload["description"],
            url=payload["url"],
            publication_date=datetime.fromisoformat(payload["publication_date"].replace("Z", "+00:00")),
            source_name=payload["source_name"],
            category=payload.get("category", []),
            relevance_score=payload.get("relevance_score", 0.0),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
        )
        session.add(article)


def upsert_summary(session: Session, article_id: str, summary: str) -> None:
    session.execute(select(Article).where(Article.id == article_id))
    session.query(Article).filter(Article.id == article_id).update({"llm_summary": summary})


def list_by_category(session: Session, category: str, limit: int) -> List[Article]:
    normalized = category.lower()
    stmt = select(Article).order_by(Article.publication_date.desc())
    articles = [article for article in session.scalars(stmt) if normalized in {c.lower() for c in article.category or []}]
    return articles[:limit]


def list_by_source(session: Session, source: str, limit: int) -> List[Article]:
    stmt = (
        select(Article)
        .where(func.lower(Article.source_name) == source.lower())
        .order_by(Article.publication_date.desc())
        .limit(limit)
    )
    return session.scalars(stmt).all()


def list_by_score(session: Session, threshold: float, limit: int) -> List[Article]:
    stmt = (
        select(Article)
        .where(Article.relevance_score >= threshold)
        .order_by(Article.relevance_score.desc())
        .limit(limit)
    )
    return session.scalars(stmt).all()


def list_by_search(session: Session, query: str, limit: int) -> List[Article]:
    tokens = [token.strip() for token in query.lower().split() if token]
    if not tokens:
        return []
    score_case = sum(
        case(
            (func.instr(func.lower(Article.title), token) > 0, 2),
            (func.instr(func.lower(Article.description), token) > 0, 1),
            else_=0,
        )
        for token in tokens
    )
    stmt = (
        select(Article)
        .order_by((Article.relevance_score * 0.5 + score_case).desc())
        .limit(limit)
    )
    return session.scalars(stmt).all()


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km


def list_by_nearby(session: Session, lat: float, lon: float, radius_km: float, limit: int) -> List[Article]:
    stmt = select(Article).where(
        and_(Article.latitude.is_not(None), Article.longitude.is_not(None))
    )
    results: List[Article] = []
    for article in session.scalars(stmt):
        distance = haversine_distance(lat, lon, article.latitude, article.longitude)  # type: ignore[arg-type]
        if distance <= radius_km:
            article.distance = distance  # type: ignore[attr-defined]
            results.append(article)
    results.sort(key=lambda a: getattr(a, "distance", float("inf")))
    return results[:limit]


def add_interaction(
    session: Session,
    article_id: str,
    event_type: str,
    weight: float,
    latitude: Optional[float],
    longitude: Optional[float],
    timestamp: datetime,
) -> None:
    session.add(
        Interaction(
            article_id=article_id,
            event_type=event_type,
            weight=weight,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp,
        )
    )


def trending_articles(session: Session, lat: float, lon: float, limit: int, window_hours: int = 24) -> List[Article]:
    time_threshold = datetime.utcnow() - timedelta(hours=window_hours)
    age_penalty = func.exp(-func.abs(func.strftime("%s", func.datetime("now")) - func.strftime("%s", Interaction.timestamp)) / 3600)

    subquery = (
        select(
            Interaction.article_id,
            func.sum(Interaction.weight * age_penalty).label("score"),
        )
        .where(Interaction.timestamp >= time_threshold)
        .group_by(Interaction.article_id)
        .subquery()
    )

    stmt = (
        select(Article, subquery.c.score)
        .join(subquery, Article.id == subquery.c.article_id)
        .order_by(subquery.c.score.desc())
        .limit(limit * 3)
    )
    candidates = session.execute(stmt).all()
    scored: List[tuple[Article, float]] = []
    for article, base_score in candidates:
        if article.latitude is None or article.longitude is None:
            continue
        distance_km = haversine_distance(lat, lon, article.latitude, article.longitude)
        geo_bonus = max(0.0, 1.0 - distance_km / 50)
        scored.append((article, float(base_score) * (1 + geo_bonus)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [article for article, _ in scored[:limit]]
