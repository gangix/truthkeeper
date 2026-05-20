from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from truthkeeper.api import companies_router, onboarding_router
from truthkeeper.config import load_runtime_env
from truthkeeper.db.bootstrap import init_db
from truthkeeper.health import router as health_router

load_runtime_env()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    try:
        from truthkeeper.onboarding.mcp_tools import build_fivetran_toolset

        build_fivetran_toolset()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(
            "MCP warmup skipped: %s. Onboarding will fail until env is fixed.", exc
        )
    yield


app = FastAPI(
    title="TruthKeeper",
    description="Cross-system reconciliation agent for B2B operations.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(companies_router)
app.include_router(onboarding_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "TruthKeeper backend. See /docs for API."}
