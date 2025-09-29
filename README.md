# Inshorts Contextual News API

This project implements a contextual news retrieval backend that demonstrates how to enrich structured news data with LLM-powered insights, rank articles across different retrieval modes, and surface location-aware trending stories.

## Features

- **LLM-assisted intent detection** – routes free-form user queries to the appropriate retrieval strategy and extracts keywords/entities (with an offline heuristic fallback).
- **Article ingestion pipeline** – loads the bundled `data.json` dataset into SQLite, generates short LLM summaries, and simulates user interaction events for trending analytics.
- **Multiple retrieval endpoints** – category, source, score threshold, semantic search, and nearby queries are supported out of the box.
- **Trending feed with caching** – computes a location-aware trending score from simulated events and caches responses by geospatial buckets.
- **RESTful FastAPI service** – exposes endpoints under `/api/v1/news` plus health checks.

## Getting Started

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the API**

   ```bash
   uvicorn app.main:app --reload
   ```

   The service will automatically create `news.db`, ingest `data.json`, populate summaries, and seed interaction events on the first launch.

3. **(Optional) Configure an LLM provider**

   Set `INSHORTS_LLM_API_KEY` to a valid OpenAI-compatible key to enable real API calls. Without a key the application uses a rule-based parser and summarizer.

## API Overview

| Endpoint | Description |
| --- | --- |
| `GET /health` | Basic health probe |
| `GET /api/v1/news/category?category=Technology&limit=5` | Latest articles within a category |
| `GET /api/v1/news/source?source=New%20York%20Times` | Latest articles from a source |
| `GET /api/v1/news/score?threshold=0.7` | Highest scoring articles above the threshold |
| `GET /api/v1/news/search?query=elon+musk` | Ranked search combining relevance score and text matches |
| `GET /api/v1/news/nearby?lat=37.4&lon=-122.1&radius_km=15` | Articles closest to a location |
| `GET /api/v1/news/trending?lat=37.4&lon=-122.1&limit=5` | Cached trending feed near a user |
| `POST /api/v1/news/query` | Free-form query that uses the LLM to determine the right retrieval mode |

### Query Resolution Payload

```json
{
  "query": "Latest developments in the Elon Musk Twitter acquisition near Palo Alto",
  "latitude": 37.4419,
  "longitude": -122.1430,
  "max_results": 5
}
```

### Sample Response

```json
[
  {
    "id": "3",
    "title": "Palo Alto prepares for autonomous vehicle pilot",
    "description": "City council in Palo Alto approves a six-month pilot for autonomous shuttles downtown.",
    "url": "https://www.example.com/palo-alto-av",
    "publication_date": "2024-04-23T12:45:00",
    "source_name": "Bay Area Daily",
    "category": ["Technology", "Local"],
    "relevance_score": 0.88,
    "latitude": 37.4419,
    "longitude": -122.143,
    "llm_summary": "Title: Palo Alto prepares for autonomous vehicle pilot. Description: City council in Palo Alto approves a six-month pilot for autonomous shuttles downtown."
  }
]
```

## Project Structure

```
app/
├── __init__.py
├── __main__.py         # Entry point for `python -m app`
├── config.py           # Settings and environment management
├── database.py         # SQLAlchemy engine/session helpers
├── llm.py              # LLM client with API + fallback modes
├── main.py             # FastAPI application and routes
├── models.py           # ORM models for articles and interactions
├── repository.py       # Data access helpers and ranking logic
├── schemas.py          # Pydantic schemas for responses & requests
└── services.py         # Ingestion pipeline, caching, service layer
```

## Testing the Service

Once the server is running you can interact with the automatic API docs at `http://127.0.0.1:8000/docs` or use curl/Postman for the endpoints listed above.
