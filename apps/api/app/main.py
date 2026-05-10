# Creates the BookFiend FastAPI application and registers health, scanning, Goodreads, and recommendation endpoints.

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.db import (
    check_database_connection,
)
from app.redis_client import (
    check_redis_connection,
)
from app.routes.goodreads import (
    router as goodreads_router,
)
from app.routes.jobs import (
    router as jobs_router,
)
from app.routes.recommendations import (
    router as recommendations_router,
)


app = FastAPI(
    title="BookFiend API",
    description=(
        "Backend API for BookFiend"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    jobs_router
)

app.include_router(
    goodreads_router
)

app.include_router(
    recommendations_router
)


@app.get("/health")
def health_check():
    check_database_connection()
    check_redis_connection()

    return {
        "api": "ok",
        "database": "ok",
        "redis": "ok",
    }