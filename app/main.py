import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import (
    chat_ui,
    chunks,
    embeddings,
    groq,
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
        embeddings.get_embedding_model,
        embeddings.DEFAULT_MODEL,
    )
    yield


app = FastAPI(
    title="RAG API",
    description="API service built with FastAPI.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(root.router)
app.include_router(chat_ui.router)
app.include_router(health.router)
app.include_router(groq.router)
app.include_router(search.router)
app.include_router(scrape.router)
app.include_router(embeddings.router)
app.include_router(ranking.router)
app.include_router(semantic_search.router)
app.include_router(chunks.router)
