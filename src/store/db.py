from __future__ import annotations

from pathlib import Path
from typing import Final

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.config import settings


_SQLITE_ASYNC_DRIVER: Final[str] = "sqlite+aiosqlite"
_POSTGRES_ASYNC_DRIVER: Final[str] = "postgresql+asyncpg"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def resolve_database_url() -> str | None:
    if settings.database_url:
        return settings.database_url

    if settings.database_backend == "disabled":
        return None

    if settings.database_backend == "sqlite":
        sqlite_path = Path(settings.sqlite_path).expanduser()
        if not sqlite_path.is_absolute():
            sqlite_path = Path(__file__).resolve().parent.parent.parent / sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"{_SQLITE_ASYNC_DRIVER}:///{sqlite_path}"

    raise RuntimeError("NEWS_DATABASE_URL is required when NEWS_DATABASE_BACKEND=postgres.")


def resolve_alembic_database_url() -> str | None:
    database_url = resolve_database_url()
    if not database_url:
        return None

    url = make_url(database_url)
    if url.drivername == _SQLITE_ASYNC_DRIVER:
        return str(url.set(drivername="sqlite"))
    if url.drivername == _POSTGRES_ASYNC_DRIVER:
        return str(url.set(drivername="postgresql+psycopg"))
    return str(url)


def get_engine() -> AsyncEngine | None:
    global _engine

    if _engine is not None:
        return _engine

    database_url = resolve_database_url()
    if not database_url:
        return None

    _engine = create_async_engine(database_url, echo=settings.database_echo, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker | None:
    global _session_factory

    if _session_factory is not None:
        return _session_factory

    engine = get_engine()
    if engine is None:
        return None

    _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
