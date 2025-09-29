from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite:///" + str((Path(__file__).resolve().parent / ".." / "news.db").resolve()))
    llm_api_key: Optional[str] = Field(default=None, env="LLM_API_KEY")
    llm_model: str = Field(default="gpt-3.5-turbo")
    trending_cache_ttl_seconds: int = Field(default=300)
    trending_cluster_precision: float = Field(default=0.5)

    class Config:
        env_prefix = "INSHORTS_"
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
