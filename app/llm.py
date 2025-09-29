from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import get_settings
from .schemas import QueryIntent

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore


@dataclass
class ParsedQuery:
    entities: List[str]
    keywords: List[str]
    locations: List[str]
    intent: str


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.settings.llm_api_key and OpenAI is not None:
            self._client = OpenAI(api_key=self.settings.llm_api_key)

    def analyze_query(self, query: str) -> QueryIntent:
        if self._client is None:
            parsed = self._fallback_parse(query)
            return QueryIntent(**parsed.__dict__)

        prompt = (
            "You are a helpful assistant that extracts structured information from user news queries.\n"
            "Return a JSON object with fields: intent (one of category, source, score, search, nearby),"
            " entities (array), locations (array), and keywords (array of important search terms)."
            " Consider proximity hints like 'near me' as the nearby intent."
            f"\nQuery: {query}\n"
        )

        response = self._client.responses.create(
            model=self.settings.llm_model,
            input=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        content = response.output[0].content[0].text  # type: ignore[attr-defined]
        data: Dict[str, List[str] | str] = json.loads(content)
        return QueryIntent(
            intent=str(data.get("intent", "search")),
            entities=[str(x) for x in data.get("entities", [])],
            locations=[str(x) for x in data.get("locations", [])],
            keywords=[str(x) for x in data.get("keywords", [])],
        )

    def summarize(self, title: str, description: str) -> str:
        text = f"Title: {title}. Description: {description}"
        if self._client is None:
            return self._fallback_summary(text)

        prompt = (
            "Provide a 1-2 sentence concise summary of the following news article."
            " Focus on the key facts.\n" + text
        )
        response = self._client.responses.create(
            model=self.settings.llm_model,
            input=[{"role": "user", "content": prompt}],
        )
        return response.output[0].content[0].text.strip()  # type: ignore[attr-defined]

    @staticmethod
    def _fallback_parse(query: str) -> ParsedQuery:
        lowered = query.lower()
        intent = "search"
        if "near" in lowered or "nearby" in lowered or "around" in lowered:
            intent = "nearby"
        elif "top" in lowered or "latest" in lowered:
            intent = "category"
        elif "from" in lowered and "news" in lowered:
            intent = "source"
        elif "score" in lowered:
            intent = "score"

        entities = re.findall(r"[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*", query)
        locations = [token for token in entities if token.lower() in {
            "palo alto", "san francisco", "paris", "tokyo", "berlin", "london", "fresno", "new york times"
        }]
        keywords = [word for word in re.split(r"\W+", query.lower()) if word and word not in {"the", "in", "from", "near", "me"}]
        return ParsedQuery(entities=entities, keywords=keywords, locations=locations, intent=intent)

    @staticmethod
    def _fallback_summary(text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        first_two = " ".join(sentences[:2])
        return first_two[:280].strip()


def get_llm_client() -> LLMClient:
    return LLMClient()
