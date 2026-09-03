"""FastAPI application with direct tool endpoints and MCP mounted."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import load_settings
from .mcp.server import build_mcp


def create_app() -> FastAPI:
    settings = load_settings()
    mcp = build_mcp(settings)
    mcp_app = mcp.http_app(path="/", stateless_http=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp_app.lifespan(mcp_app):
            yield

    app = FastAPI(title="Shopping-AI Stateless MCP", version="0.1.0", lifespan=lifespan)
    app.get("/health")(lambda: {"status": "ok"})
    app.mount("/mcp", mcp_app)
    return app


app = create_app()
