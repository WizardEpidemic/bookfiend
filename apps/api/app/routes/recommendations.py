# Exposes personalized BookFiend recommendations generated from imported Goodreads preferences.

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.goodreads_book import (
    GoodreadsBook,
)
from app.schemas.recommendations import (
    RecommendationResponse,
)
from app.services.recommendations import (
    generate_recommendations,
)


router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)


@router.get(
    "",
    response_model=(
        RecommendationResponse
    ),
)
def get_recommendations(
    limit: int = Query(
        default=8,
        ge=1,
        le=20,
    ),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    books = list(
        db.scalars(
            select(
                GoodreadsBook
            )
        ).all()
    )

    result = (
        generate_recommendations(
            books,
            limit=limit,
        )
    )

    return RecommendationResponse(
        **result
    )