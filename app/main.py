from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import engine, init_db
from app.graph.build import build_proposal_graph
from app.routers import health, knowledge, proposals


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.graph = build_proposal_graph()
    yield
    await engine.dispose()


def _parse_cors_origins(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or ["http://localhost:3000"]


app = FastAPI(title="Sales Proposal Generator API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(proposals.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
