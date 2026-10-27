from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to the RAG API"}
