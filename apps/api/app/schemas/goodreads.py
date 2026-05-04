# Defines API responses for Goodreads CSV imports and generated preference summaries.

from pydantic import BaseModel


class GoodreadsImportResponse(
    BaseModel
):
    imported_count: int
    rated_count: int
    shelf_count: int
    favorite_authors: list[str]
    favorite_shelves: list[str]