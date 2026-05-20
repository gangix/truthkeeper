"""Smoke test: ADK SequentialAgent with a tool-using sub-agent + an output_schema sub-agent.

If this works, the production onboarding pipeline (Discovery -> Profiling ->
Synthesis) is structurally feasible. If it fails, fall back to chaining two
separate Runner.run_async calls in pipeline.py.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-3.1-pro-preview")
APP_NAME = "truthkeeper-validation"
USER_ID = "validator"
SESSION_ID = "hello-sequential-session"


def list_fruits() -> dict:
    """Returns a small fixed list of fruits as a tool result."""
    return {"fruits": ["apple", "banana", "cherry"]}


class FruitSummary(BaseModel):
    count: int
    fruits: list[str]
    summary: str


async def main() -> None:
    collector = LlmAgent(
        name="collector",
        model=MODEL_ID,
        description="Collects fruits via the list_fruits tool.",
        instruction=(
            "Call the list_fruits tool exactly once, then respond with a "
            "short plain-English sentence describing what you found. The "
            "tool's output is already stored; you do not need to repeat it "
            "verbatim."
        ),
        tools=[FunctionTool(func=list_fruits)],
        output_key="discovered_fruits",
    )

    summarizer = LlmAgent(
        name="summarizer",
        model=MODEL_ID,
        description="Produces a structured FruitSummary from session state.",
        instruction=(
            "Read the prior agent's discovery in session state under key "
            "'discovered_fruits'. Produce a FruitSummary JSON with the count, "
            "the list of fruit names, and a one-sentence summary."
        ),
        output_schema=FruitSummary,
    )

    pipeline = SequentialAgent(
        name="hello_sequential",
        sub_agents=[collector, summarizer],
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(agent=pipeline, app_name=APP_NAME, session_service=session_service)

    prompt = "List the available fruits and summarize."
    content = types.Content(role="user", parts=[types.Part(text=prompt)])

    print(f"\n>>> Prompt: {prompt}\n")
    final_text: str | None = None
    tool_was_called = False
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        author = event.author or "?"
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            print(f"  [{author} final] {text[:200]}")
            if author == "summarizer":
                final_text = text
        elif event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"  [{author} call] {part.function_call.name}({part.function_call.args})")
                    if part.function_call.name == "list_fruits":
                        tool_was_called = True
                elif part.function_response:
                    print(f"  [{author} result] {part.function_response.name} -> (truncated)")

    if not tool_was_called:
        raise SystemExit("ERROR: collector did not invoke list_fruits — tool routing is broken")

    if not final_text:
        raise SystemExit("ERROR: no final response from pipeline")

    try:
        parsed = FruitSummary.model_validate_json(final_text)
    except Exception as exc:
        raise SystemExit(
            f"ERROR: summarizer output did not parse as FruitSummary: {exc}\n"
            f"Raw text: {final_text!r}"
        ) from None
    print(f"\n<<< Parsed FruitSummary: {parsed.model_dump_json(indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
