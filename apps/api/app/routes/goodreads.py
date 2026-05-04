# Implements Goodreads CSV import and persists normalized reading-history records.

from collections import Counter

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.goodreads_book import (
    GoodreadsBook,
)
from app.schemas.goodreads import (
    GoodreadsImportResponse,
)
from app.services.goodreads import (
    parse_goodreads_csv,
)


router = APIRouter(
    prefix="/goodreads",
    tags=["goodreads"],
)


@router.post(
    "/import",
    response_model=(
        GoodreadsImportResponse
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
async def import_goodreads(
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> GoodreadsImportResponse:
    contents = await csv_file.read()

    if not contents:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Uploaded Goodreads CSV is empty."
            ),
        )

    try:
        records = parse_goodreads_csv(
            contents
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    if not records:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "No valid Goodreads book rows were found."
            ),
        )

    # The sprint version treats the latest import as the active profile.
    db.execute(
        delete(GoodreadsBook)
    )

    books = [
        GoodreadsBook(**record)
        for record in records
    ]

    db.add_all(books)
    db.commit()

    rated_books = [
        record
        for record in records
        if record["my_rating"]
        is not None
    ]

    positively_rated = [
        record
        for record in rated_books
        if record["my_rating"]
        >= 4
    ]

    author_counts = Counter(
        record["author"]
        for record in (
            positively_rated
            or rated_books
            or records
        )
    )

    shelf_counts = Counter(
        shelf
        for record in (
            positively_rated
            or rated_books
            or records
        )
        for shelf in record[
            "bookshelves"
        ]
    )

    return GoodreadsImportResponse(
        imported_count=len(records),
        rated_count=len(
            rated_books
        ),
        shelf_count=len(
            shelf_counts
        ),
        favorite_authors=[
            author
            for author, _
            in author_counts.most_common(
                5
            )
        ],
        favorite_shelves=[
            shelf
            for shelf, _
            in shelf_counts.most_common(
                8
            )
        ],
    )