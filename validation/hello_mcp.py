"""Critical path validation: ADK + Gemini 3 + Fivetran MCP via stdio.

Success criterion: Gemini 3 receives the Fivetran MCP tools, picks one
appropriate tool (list_connections / list_groups), invokes it, and returns
a coherent natural-language answer derived from the tool result.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

load_dotenv(Path(__file__).parent / ".env")

MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-3.1-pro-preview")
APP_NAME = "truthkeeper-validation"
USER_ID = "validator"
SESSION_ID = "hello-mcp-session"


def build_fivetran_toolset() -> McpToolset:
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


async def main() -> None:
    missing = [k for k in ("FIVETRAN_API_KEY", "FIVETRAN_API_SECRET") if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"ERROR: required env vars not set: {', '.join(missing)}. "
            "Copy validation/.env.example to validation/.env and fill in your Fivetran credentials."
        )
    toolset = build_fivetran_toolset()
    agent = LlmAgent(
        name="fivetran_explorer",
        model=MODEL_ID,
        description="An agent that can inspect Fivetran connectors via MCP.",
        instruction=(
            "You have access to Fivetran's MCP tools. When asked about "
            "connections or groups, use the appropriate tool to fetch the "
            "answer. Always cite the tool you used."
        ),
        tools=[toolset],
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        agent=agent, app_name=APP_NAME, session_service=session_service
    )

    prompt = "What Fivetran groups exist in this account? List them with IDs."
    content = types.Content(role="user", parts=[types.Part(text=prompt)])

    print(f"\n>>> Prompt: {prompt}\n")
    try:
        async for event in runner.run_async(
            user_id=USER_ID, session_id=SESSION_ID, new_message=content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                print(f"\n<<< Final response:\n{event.content.parts[0].text}\n")
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        print(f"  [tool call] {part.function_call.name}({part.function_call.args})")
                    elif part.function_response:
                        print(f"  [tool result] {part.function_response.name} → (truncated)")
    finally:
        await toolset.close()


if __name__ == "__main__":
    asyncio.run(main())
