# Parses Goodreads CSV exports and converts their real export fields into normalized BookFiend records.

import csv
import io
import re
from datetime import datetime
from typing import Any


GOODREADS_REQUIRED_COLUMNS = {
    "Title",
    "Author",
}

GOODREADS_OPTIONAL_COLUMNS = {
    "ISBN",
    "ISBN13",
    "My Rating",
    "Bookshelves",
    "Date Read",
}


def clean_goodreads_isbn(
    value: str | None,
) -> str | None:
    if not value:
        return None

    cleaned = value.strip()

    match = re.fullmatch(
        r'="\s*([^"]+)\s*"',
        cleaned,
    )

    if match:
        cleaned = match.group(1)

    cleaned = re.sub(
        r"[^0-9Xx]",
        "",
        cleaned,
    )

    return cleaned or None


def parse_rating(
    value: str | None,
) -> float | None:
    if not value:
        return None

    try:
        rating = float(value)

        if rating <= 0:
            return None

        return rating

    except ValueError:
        return None


def parse_shelves(
    value: str | None,
) -> list[str]:
    if not value:
        return []

    shelves = [
        shelf.strip()
        for shelf in value.split(",")
        if shelf.strip()
    ]

    return sorted(set(shelves))


def parse_date_read(
    value: str | None,
):
    if not value:
        return None

    value = value.strip()

    formats = (
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%m/%d/%Y",
    )

    for date_format in formats:
        try:
            return datetime.strptime(
                value,
                date_format,
            ).date()
        except ValueError:
            continue

    return None


def parse_goodreads_csv(
    contents: bytes,
) -> list[dict[str, Any]]:
    try:
        text = contents.decode(
            "utf-8-sig"
        )
    except UnicodeDecodeError:
        text = contents.decode(
            "latin-1"
        )

    reader = csv.DictReader(
        io.StringIO(text)
    )

    fieldnames = set(
        reader.fieldnames or []
    )

    missing_columns = (
        GOODREADS_REQUIRED_COLUMNS
        - fieldnames
    )

    if missing_columns:
        missing = ", ".join(
            sorted(missing_columns)
        )

        raise ValueError(
            f"Missing required Goodreads columns: {missing}"
        )

    records: list[
        dict[str, Any]
    ] = []

    for row in reader:
        title = (
            row.get("Title") or ""
        ).strip()

        author = (
            row.get("Author") or ""
        ).strip()

        if not title or not author:
            continue

        records.append(
            {
                "title": title,
                "author": author,
                "isbn": (
                    clean_goodreads_isbn(
                        row.get("ISBN")
                    )
                ),
                "isbn13": (
                    clean_goodreads_isbn(
                        row.get("ISBN13")
                    )
                ),
                "my_rating": (
                    parse_rating(
                        row.get(
                            "My Rating"
                        )
                    )
                ),
                "bookshelves": (
                    parse_shelves(
                        row.get(
                            "Bookshelves"
                        )
                    )
                ),
                "date_read": (
                    parse_date_read(
                        row.get(
                            "Date Read"
                        )
                    )
                ),
                "raw_row": {
                    key: value
                    for key, value
                    in row.items()
                    if key is not None
                },
            }
        )

    return records