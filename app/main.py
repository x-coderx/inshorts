from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .llm import get_llm_client
from .schemas import ArticleResponse, QueryRequest
from .services import (
    get_articles_by_category,
    get_articles_by_score,
    get_articles_by_search,
    get_articles_by_source,
    get_articles_nearby,
    get_trending_articles,
    load_data,
    resolve_query,
)

Base.metadata.create_all(bind=engine)
load_data()

app = FastAPI(title="Inshorts Contextual News API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CATEGORY_KEYWORDS = {
    "technology",
    "business",
    "world",
    "general",
    "local",
    "environment",
    "policy",
    "sustainability",
}


@app.get("/api/v1/news/category", response_model=list[ArticleResponse])
def news_by_category(category: str = Query(..., description="Category name"), limit: int = 5) -> list[ArticleResponse]:
    articles = get_articles_by_category(category, limit)
    if not articles:
        raise HTTPException(status_code=404, detail="No articles found for category")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.get("/api/v1/news/source", response_model=list[ArticleResponse])
def news_by_source(source: str = Query(..., description="Source name"), limit: int = 5) -> list[ArticleResponse]:
    articles = get_articles_by_source(source, limit)
    if not articles:
        raise HTTPException(status_code=404, detail="No articles found for source")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.get("/api/v1/news/score", response_model=list[ArticleResponse])
def news_by_score(threshold: float = Query(0.7, ge=0.0, le=1.0), limit: int = 5) -> list[ArticleResponse]:
    articles = get_articles_by_score(threshold, limit)
    if not articles:
        raise HTTPException(status_code=404, detail="No articles found above threshold")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.get("/api/v1/news/search", response_model=list[ArticleResponse])
def news_by_search(query: str = Query(..., description="Search query"), limit: int = 5) -> list[ArticleResponse]:
    articles = get_articles_by_search(query, limit)
    if not articles:
        raise HTTPException(status_code=404, detail="No articles found for search query")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.get("/api/v1/news/nearby", response_model=list[ArticleResponse])
def news_by_nearby(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(10.0, gt=0),
    limit: int = 5,
) -> list[ArticleResponse]:
    articles = get_articles_nearby(lat, lon, radius_km, limit)
    if not articles:
        raise HTTPException(status_code=404, detail="No nearby articles found")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.get("/api/v1/news/trending", response_model=list[ArticleResponse])
def trending(lat: float = Query(...), lon: float = Query(...), limit: int = 5) -> list[ArticleResponse]:
    articles = get_trending_articles(lat, lon, limit)
    if not articles:
        raise HTTPException(status_code=404, detail="No trending articles found")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.post("/api/v1/news/query", response_model=list[ArticleResponse])
def resolve_user_query(payload: QueryRequest, llm=Depends(get_llm_client)) -> list[ArticleResponse]:
    parsed = llm.analyze_query(payload.query)

    value = None
    if parsed.intent == "category":
        value = next((kw for kw in parsed.keywords if kw.lower() in _CATEGORY_KEYWORDS), None)
        if value:
            value = value.capitalize()
    elif parsed.intent == "source" and parsed.entities:
        value = parsed.entities[0]
    elif parsed.intent == "score":
        value = next((token for token in parsed.keywords if token.replace('.', '', 1).isdigit()), None)
    else:
        value = payload.query

    articles = resolve_query(parsed.intent, value, payload.latitude, payload.longitude, payload.max_results)
    if not articles:
        raise HTTPException(status_code=404, detail="No articles matched the query")
    return [ArticleResponse.from_orm(article) for article in articles]


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
