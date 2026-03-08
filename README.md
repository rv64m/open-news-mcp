# Open News MCP

Open News MCP is a news-focused MCP server for collecting market and macro news, normalizing it into a local database, embedding it into a vector store, and exposing structured and semantic retrieval tools to LLM clients.

It is designed for workflows where an agent needs to:

- discover available news sources,
- browse recent news with explicit filters,
- search semantically related news,
- inspect clusters of related stories as a graph.

## Why This Project Exists

Most news APIs are optimized for either raw aggregation or UI consumption. MCP-oriented agents need something different:

- stable, tool-friendly method contracts,
- deterministic metadata such as source, tier, category, and language,
- local persistence for repeatable queries,
- semantic retrieval over already-ingested news,
- operational simplicity for self-hosted setups.

Open News MCP fills that gap.

## Core Capabilities

- RSS-based ingestion from a curated source catalog in [`src/core/feeds.py`](src/core/feeds.py)
- Persistent storage in SQLite or PostgreSQL
- Alembic-based schema management
- Local or pluggable embedding backend abstraction
- Qdrant-backed vector search
- MCP tools for source discovery, structured browsing, and related-news graph search
- One-shot and long-running sync workers

## System Design

### Architecture

```mermaid
flowchart LR
    A[Curated RSS Sources] --> B[Sync Worker]
    B --> C[Normalized News Storage]
    B --> D[Source Catalog]
    B --> E[Embedding Pipeline]
    E --> F[Qdrant Vector Store]
    C --> G[MCP Server]
    D --> G
    F --> G
    G --> H[LLM / MCP Client]
```

### Data Flow

1. `commands/sync.py` selects configured sources from the source catalog.
2. RSS entries are fetched, normalized, and deduplicated by `url_hash`.
3. New rows are stored in `news_articles`, and sources are upserted into `sources`.
4. If `--embed` is enabled, newly inserted rows are embedded immediately.
5. Vectors are written into Qdrant using a stable point id derived from the article URL.
6. The MCP server exposes retrieval methods over the database and vector store.

### Main Layers

- Ingestion layer: [`commands/sync.py`](commands/sync.py)
- Source definitions: [`src/core/feeds.py`](src/core/feeds.py)
- Persistent storage: [`src/store/`](src/store)
- Embedding abstraction: [`src/embedding/`](src/embedding)
- Vector abstraction: [`src/vector/`](src/vector)
- MCP tools: [`src/tools/`](src/tools)
- Server entrypoint: [`server.py`](server.py)

## Quick Start

### Requirements

- Python `3.13+`
- [`uv`](https://github.com/astral-sh/uv)
- A database:
  - SQLite for local development, or
  - PostgreSQL for a multi-process / production deployment
- Qdrant if you want semantic retrieval and related-news graph search

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure the Environment

Create your local environment file from the example:

```bash
cp .env.example .env
```

For a minimal SQLite setup:

```bash
NEWS_HOST=127.0.0.1
NEWS_PORT=10110
NEWS_TRANSPORT=streamable-http

NEWS_DATABASE_BACKEND=sqlite
NEWS_SQLITE_PATH=data/news.db

NEWS_EMBEDDING_BACKEND=local
NEWS_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
NEWS_EMBEDDING_DEVICE=cpu

NEWS_VECTOR_BACKEND=qdrant
NEWS_VECTOR_COLLECTION=news_articles
NEWS_QDRANT_URL=http://127.0.0.1:6333
```

For PostgreSQL:

```bash
NEWS_DATABASE_BACKEND=postgres
NEWS_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/open_news_mcp
```

### 3. Start Qdrant

The simplest local option is Docker. Qdrant’s official quickstart shows:

```bash
docker pull qdrant/qdrant

docker run -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
  qdrant/qdrant
```

Once started:

- REST API: `http://127.0.0.1:6333`
- Web UI: `http://127.0.0.1:6333/dashboard`
- gRPC: `127.0.0.1:6334`

Official reference:

- https://qdrant.tech/documentation/quick-start/

If you prefer embedded local storage instead of a remote Qdrant process, set:

```bash
NEWS_QDRANT_PATH=data/qdrant
```

### 4. Run Database Migrations

For SQLite:

```bash
uv run alembic upgrade head
```

For PostgreSQL using the Postgres-oriented Alembic config:

```bash
uv run alembic -c alembic.postgres.ini upgrade head
```

You can also let the MCP server auto-apply migrations at startup:

```bash
NEWS_DATABASE_AUTO_MIGRATE=true
```

### 5. Sync News

One-shot sync:

```bash
uv run python commands/sync.py --once
```

One-shot sync plus embedding:

```bash
uv run python commands/sync.py --once --embed
```

Long-running sync loop:

```bash
uv run python commands/sync.py --loop
```

Long-running sync loop with embedding:

```bash
uv run python commands/sync.py --loop --embed
```

Useful flags:

- `--categories markets crypto centralbanks`
- `--sources "Federal Reserve" "Reuters Markets"`
- `--verbose`

### 6. Start the MCP Server

```bash
uv run python server.py
```

The server exposes MCP tools over the configured transport. By default:

- host: `127.0.0.1`
- port: `10110`
- transport: `streamable-http`

## Running with PM2

PM2 is useful when you want to keep both the MCP server and the sync loop alive on a single host.

### Option A: Simple PM2 Commands

Start the MCP server:

```bash
pm2 start "uv run python server.py" --name open-news-mcp-server
```

Start the sync loop:

```bash
pm2 start "uv run python commands/sync.py --loop --embed" --name open-news-mcp-sync
```

Persist the process list:

```bash
pm2 save
pm2 startup
```

### Option B: PM2 Ecosystem File

Create `ecosystem.config.js`:

```js
module.exports = {
  apps: [
    {
      name: "open-news-mcp-server",
      cwd: "/absolute/path/to/open-news-mcp",
      script: "uv",
      args: "run python server.py",
      interpreter: "none",
      env: {
        NEWS_HOST: "127.0.0.1",
        NEWS_PORT: "10110",
        NEWS_TRANSPORT: "streamable-http"
      }
    },
    {
      name: "open-news-mcp-sync",
      cwd: "/absolute/path/to/open-news-mcp",
      script: "uv",
      args: "run python commands/sync.py --loop --embed",
      interpreter: "none"
    }
  ]
};
```

Then start it:

```bash
pm2 start ecosystem.config.js
pm2 save
```

## MCP Features

The MCP server currently registers three tools:

### `list_sources`

Purpose:

- discover which sources are available in the local source catalog
- filter by `categories`, `tiers`, `language`, and `limit`

Why it exists:

- LLMs should not guess source names
- source selection should be explicit and inspectable

Implementation:

- tool: [`src/tools/sources.py`](src/tools/sources.py)
- store query: [`src/store/sources.py`](src/store/sources.py)

### `search_news`

Purpose:

- browse normalized news articles with deterministic filters

Supported filters:

- `published_after`
- `timespan`
- `categories`
- `sources`
- `tiers`
- `language`
- `sort`

Design intent:

- this is the structured retrieval tool
- it does not perform fuzzy or semantic matching
- it is useful when an agent already knows the scope it wants

Implementation:

- tool: [`src/tools/search.py`](src/tools/search.py)
- repository: [`src/store/repository.py`](src/store/repository.py)

### `query_related_news_graph`

Purpose:

- retrieve semantically related news from the vector store
- return the result as a graph instead of a flat list

Input:

- `query`
- `limit`
- `published_after`
- `timespan`
- `categories`
- `sources`
- `tiers`
- `language`

Output shape:

- `graph.nodes`
- `graph.edges`

Graph semantics:

- one query node
- article nodes returned from vector retrieval
- `query_match` edges from the query to each article
- `related` edges between articles that are semantically close to each other

Design intent:

- support agent reasoning over clusters, not just rankings
- expose story neighborhoods that are easier to summarize, compare, and route to downstream logic

Implementation:

- tool: [`src/tools/query.py`](src/tools/query.py)

## Storage Model

### Database Tables

- `sources`
  - source catalog metadata
  - category, tier, language, feed URL, tags
- `news_articles`
  - normalized article rows
  - deduplicated by `url_hash`
  - tracks `is_embedded` so newly inserted or updated rows can be re-embedded

### Vector Storage

Qdrant points currently store:

- `article_id`
- `url`
- `title`
- `source`
- `category`
- `tier`
- `domain`
- `published_at`

Point ids are derived from the article URL, which keeps upserts stable across repeated syncs.

## Sync and Scheduling Model

The sync worker uses tier-aware in-process scheduling:

- tier `1`: every `5` minutes
- tier `2`: every `10` minutes
- tier `3+`: every `30` minutes

This keeps high-signal sources fresher without forcing the whole catalog into the same polling interval.

When `--embed` is enabled:

- only newly inserted articles from the current sync cycle are embedded
- the worker does not rescan the full historical backlog on every loop

## Local Development

### Useful Commands

```bash
uv sync
uv run alembic upgrade head
uv run python commands/sync.py --once --embed
uv run python server.py
uv run python -m compileall src commands server.py
```

### Notebooks

The `playground/` directory contains example notebooks for local exploration:

- [`playground/search_news.ipynb`](playground/search_news.ipynb)
- [`playground/query_news.ipynb`](playground/query_news.ipynb)
- [`playground/query_related_news_graph.ipynb`](playground/query_related_news_graph.ipynb)

## Project Structure

```text
.
├── alembic/                 # schema migrations
├── commands/                # operational commands such as sync
├── playground/              # notebooks for local experimentation
├── src/
│   ├── core/                # curated feeds and upstream helpers
│   ├── embedding/           # embedding abstraction and providers
│   ├── store/               # database models and repositories
│   ├── tools/               # MCP tool implementations
│   └── vector/              # vector store abstraction and providers
├── .env.example
├── server.py                # MCP server entrypoint
└── README.md
```

## Operational Notes

### SQLite vs PostgreSQL

Use SQLite when:

- you are developing locally
- you run a single process
- you want the simplest setup

Use PostgreSQL when:

- you want a more production-oriented database
- you run multiple processes
- you want clearer operational separation between app and storage

### Local Embedding Models

The default local example uses:

- `Qwen/Qwen3-Embedding-0.6B`

This is a reasonable balance between local deployability and retrieval quality. You can swap it by changing `NEWS_EMBEDDING_MODEL`.

### Logging

The sync worker defaults to `INFO`.

- `--verbose` enables `DEBUG`
- `httpx` request logs are suppressed by default
- transformer and sentence-transformers startup noise is reduced in normal runs

## Limitations

- Remote embedding providers are reserved in config but not implemented yet
- RSS availability and quality vary by upstream source
- There is no dedicated reranker yet
- Related-news graph edges are currently built from post-retrieval semantic similarity rather than a separate graph index
- The old `playground/query_news.ipynb` reflects an earlier list-based semantic query workflow; the graph notebook is the preferred path for related-news exploration

## Contributing

Issues and pull requests are welcome. Good contribution targets include:

- new source catalog entries,
- better semantic clustering or reranking,
- more vector backends,
- improved filtering in vector search,
- production deployment recipes,
- richer MCP tool metadata and examples.
