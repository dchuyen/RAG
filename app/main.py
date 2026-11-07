import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.services import embeddings as embedding_service
from app.routers import (
    chat_ui,
    chunks,
    embeddings,
    gemini,
    health,
    ranking,
    root,
    scrape,
    search,
    semantic_search,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(
        embedding_service.get_embedding_model,
        embedding_service.DEFAULT_MODEL,
    )
    yield


app = FastAPI(
    title="RAG API",
    description="API service built with FastAPI.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)

app.include_router(root.router)
app.include_router(chat_ui.router)
app.include_router(health.router)
app.include_router(gemini.router)
app.include_router(search.router)
app.include_router(scrape.router)
app.include_router(embeddings.router)
app.include_router(ranking.router)
app.include_router(semantic_search.router)
app.include_router(chunks.router)
