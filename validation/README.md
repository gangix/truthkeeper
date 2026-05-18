# validation/

Throwaway scripts that prove integrations work before we build on them.

## hello_mcp.py — Day 1 critical path

Proves: ADK + Gemini 3.1 Pro on Vertex AI + Fivetran's official stdio MCP server work together.

### Run

Requires `uv` installed (`brew install uv` or `pip install uv`).

1. Copy `.env.example` to `.env` and fill in credentials.
2. `gcloud auth application-default login`
3. `uv run python hello_mcp.py`

Expected: agent lists Fivetran groups using the `list_groups` MCP tool.

If this script doesn't work, **do not proceed with the rest of the build** —
the partner integration is structurally broken and the architecture must
fall back to mcp-proxy (Path B) or direct REST (Path C) per the spec.
