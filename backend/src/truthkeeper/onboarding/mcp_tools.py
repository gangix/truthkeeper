"""Fivetran MCP toolset attachment, lifted from validation/hello_mcp.py.

Used by DiscoveryAgent. The McpToolset spawns a `uvx --from
git+https://github.com/fivetran/fivetran-mcp fivetran-mcp` subprocess over
stdio. Cold-start cost is 20-40s; main.py lifespan warms it on boot.
"""

from __future__ import annotations

import os

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


def build_fivetran_toolset() -> McpToolset:
    missing = [
        k for k in ("FIVETRAN_API_KEY", "FIVETRAN_API_SECRET") if not os.environ.get(k)
    ]
    if missing:
        raise RuntimeError(
            f"Cannot build Fivetran MCP toolset: missing env vars: {', '.join(missing)}. "
            "Set them in validation/.env (local) or Cloud Run env (prod)."
        )
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uvx",
                args=[
                    "--from",
                    "git+https://github.com/fivetran/fivetran-mcp",
                    "fivetran-mcp",
                ],
                env={
                    "FIVETRAN_API_KEY": os.environ["FIVETRAN_API_KEY"],
                    "FIVETRAN_API_SECRET": os.environ["FIVETRAN_API_SECRET"],
                    "PATH": os.environ["PATH"],
                },
            ),
            timeout=60,
        ),
    )
