from mcp.server.fastmcp import FastMCP

from src.config import settings
from src.store.db import resolve_database_url
from src.tools.query import query_news, query_related_news_graph
from src.tools.search import search_news
from src.tools.sources import (
    list_categories,
    list_filter_metadata,
    list_source_names,
    list_sources,
    list_tiers,
)


mcp = FastMCP("news", host=settings.host, port=settings.port)
mcp.add_tool(search_news)
mcp.add_tool(query_news)
mcp.add_tool(query_related_news_graph)
mcp.add_tool(list_sources)
mcp.add_tool(list_categories)
mcp.add_tool(list_tiers)
mcp.add_tool(list_source_names)
mcp.add_tool(list_filter_metadata)


def main() -> None:
    if settings.database_auto_migrate and resolve_database_url():
        from alembic import command
        from alembic.config import Config

        config = Config("alembic.ini")
        command.upgrade(config, "head")
    mcp.run(transport=settings.transport)


if __name__ == "__main__":
    main()
