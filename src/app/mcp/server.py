"""FastMCP server instance and immutable capability wiring."""

from __future__ import annotations

from ..config import Settings
from ..context import new_trace_id
from .tools import register_tools


def build_mcp(settings: Settings):
    from fastmcp import FastMCP
    from fastmcp.server.middleware import Middleware

    class InvalidInputMiddleware(Middleware):
        async def on_call_tool(self, context, call_next):
            from fastmcp.exceptions import ValidationError
            from fastmcp.tools.base import ToolResult

            try:
                return await call_next(context)
            except ValidationError as exc:
                envelope = {
                    "trace_id": new_trace_id(),
                    "ok": False,
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": str(exc) or "Invalid tool arguments",
                        "retryable": False,
                    },
                }
                return ToolResult(structured_content=envelope, is_error=True)

    server = FastMCP(name="symy-shopping", instructions="Stateless shopping tools for the Symy brain.")
    register_tools(server, settings)
    server.add_middleware(InvalidInputMiddleware())
    return server
