from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from truthkeeper.api import companies_router
from truthkeeper.health import router as health_router

app = FastAPI(
    title="TruthKeeper",
    description="Cross-system reconciliation agent for B2B operations.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon scope: no auth, public demo
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(companies_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "TruthKeeper backend. See /docs for API."}
