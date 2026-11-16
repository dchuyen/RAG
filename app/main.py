import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import chat_ui, embeddings, gemini, health, semantic_search
from app.services.embeddings import DEFAULT_MODEL, preload_embedding_model

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Đang nạp mô hình embedding '%s' khi khởi động server...", DEFAULT_MODEL)
    preload_embedding_model(DEFAULT_MODEL)
    logger.info("Nạp mô hình embedding thành công.")
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

app.include_router(chat_ui.router)
app.include_router(gemini.router)
app.include_router(health.router)
app.include_router(embeddings.router)
app.include_router(semantic_search.router)
