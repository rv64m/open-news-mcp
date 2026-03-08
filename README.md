# open-news-mcp

News MCP server backed by the world news.

## Setup

```bash
uv sync --package news-mcp
```

## Run

```bash
uv run --package news-mcp python -m servers.news.server
```

## Environment

Copy `servers/news/.env.example` to `servers/news/.env` and adjust as needed.

## Database

This service can persist normalized news rows into `sqlite` or `postgres`.

```bash
# SQLite
NEWS_DATABASE_BACKEND=sqlite
NEWS_SQLITE_PATH=data/news.db

# Postgres
NEWS_DATABASE_BACKEND=postgres
NEWS_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/news_mcp
```

Run migrations with Alembic:

```bash
uv run alembic upgrade head
```

Use the Postgres-flavored Alembic config when you want a Postgres default:

```bash
uv run alembic -c alembic.postgres.ini upgrade head
```

Or let the server apply pending migrations at startup:

```bash
NEWS_DATABASE_AUTO_MIGRATE=true
```

## Feed Sync

One-shot sync:

```bash
uv run python commands/sync.py --once
```

Loop worker with in-process scheduling:

```bash
uv run python commands/sync.py --loop
```

`sync.py` will upsert the source catalog and insert new articles into the local database. Pass `--embed` when you want the same run to vectorize newly inserted news after each sync cycle.
