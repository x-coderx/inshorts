from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ArticleBase(BaseModel):
    id: str
    title: str
    description: str
    url: str
    publication_date: datetime
    source_name: str
    category: List[str]
    relevance_score: float
    latitude: Optional[float]
    longitude: Optional[float]
    llm_summary: Optional[str] = Field(default=None)


class ArticleResponse(ArticleBase):
    class Config:
        orm_mode = True


class QueryRequest(BaseModel):
    query: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    max_results: int = Field(default=5, ge=1, le=20)


class QueryIntent(BaseModel):
    intent: str
    entities: List[str]
    locations: List[str]
    keywords: List[str]
