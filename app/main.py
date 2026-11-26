import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import chat_ui, embeddings, gemini, semantic_search
from app.services.query_cache import run_query_cache_cleanup

logger = logging.getLogger(__name__)


def _log_cache_cleanup_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error(
            "Tác vụ dọn cache đã dừng do lỗi.",
            exc_info=(type(error), error, error.__traceback__),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.ranking import preload_cross_encoder
    from app.services.embeddings import preload_embedding_model

    logger.info("Đang nạp trước mô hình cross-encoder và embedding...")
    preload_cross_encoder()
    preload_embedding_model()
    logger.info("Đã nạp xong các mô hình AI khi khởi động server.")

    cache_cleanup_task = asyncio.create_task(run_query_cache_cleanup())
    cache_cleanup_task.add_done_callback(_log_cache_cleanup_failure)
    try:
        yield
    finally:
        cache_cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cache_cleanup_task


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
app.include_router(embeddings.router)
app.include_router(semantic_search.router)
