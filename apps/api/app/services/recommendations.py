# Builds Goodreads preference profiles and ranks seeded books using TF-IDF cosine similarity.

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.goodreads_book import GoodreadsBook


CATALOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "recommendation_catalog.json"
)


def _normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _load_catalog() -> list[dict[str, Any]]:
    with CATALOG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def _book_document(
    title: str,
    author: str,
    genres: list[str],
    description: str = "",
) -> str:
    genre_text = " ".join(genres)

    return " ".join(
        [
            title,
            author,
            genre_text,
            genre_text,
            description,
        ]
    )


def _build_profile_document(
    books: list[GoodreadsBook],
) -> str:
    profile_parts: list[str] = []

    for book in books:
        rating = (
            book.my_rating
            if book.my_rating is not None
            else 3
        )

        if rating < 3:
            continue

        weight = 3 if rating >= 5 else 2 if rating >= 4 else 1

        document = _book_document(
            book.title,
            book.author,
            book.bookshelves,
        )

        profile_parts.extend(
            [document] * weight
        )

    return " ".join(profile_parts)


def _known_books(
    books: list[GoodreadsBook],
) -> set[tuple[str, str]]:
    return {
        (
            _normalize(book.title),
            _normalize(book.author),
        )
        for book in books
    }


def _favorite_shelves(
    books: list[GoodreadsBook],
) -> Counter[str]:
    counts: Counter[str] = Counter()

    for book in books:
        if (
            book.my_rating is not None
            and book.my_rating < 4
        ):
            continue

        for shelf in book.bookshelves:
            counts[shelf] += 1

    return counts


def _favorite_authors(
    books: list[GoodreadsBook],
) -> Counter[str]:
    counts: Counter[str] = Counter()

    for book in books:
        if (
            book.my_rating is not None
            and book.my_rating < 4
        ):
            continue

        counts[book.author] += 1

    return counts


def generate_recommendations(
    books: list[GoodreadsBook],
    limit: int = 8,
) -> dict[str, Any]:
    if not books:
        return {
            "profile_book_count": 0,
            "candidate_count": 0,
            "recommendations": [],
        }

    catalog = _load_catalog()
    known = _known_books(books)

    candidates = [
        book
        for book in catalog
        if (
            _normalize(book["title"]),
            _normalize(book["author"]),
        )
        not in known
    ]

    profile_document = (
        _build_profile_document(
            books
        )
    )

    candidate_documents = [
        _book_document(
            candidate["title"],
            candidate["author"],
            candidate["genres"],
            candidate["description"],
        )
        for candidate in candidates
    ]

    corpus = [
        profile_document,
        *candidate_documents,
    ]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
    )

    matrix = vectorizer.fit_transform(
        corpus
    )

    similarities = cosine_similarity(
        matrix[0:1],
        matrix[1:],
    )[0]

    shelf_counts = (
        _favorite_shelves(
            books
        )
    )

    author_counts = (
        _favorite_authors(
            books
        )
    )

    ranked = []

    for candidate, similarity in zip(
        candidates,
        similarities,
    ):
        overlapping_genres = [
            genre
            for genre in candidate[
                "genres"
            ]
            if shelf_counts[genre] > 0
        ]

        genre_support = sum(
            shelf_counts[genre]
            for genre in overlapping_genres
        )

        genre_score = min(
            genre_support / 5,
            1.0,
        )

        author_score = (
            1.0
            if author_counts[
                candidate["author"]
            ]
            > 0
            else 0.0
        )

        final_score = (
            float(similarity) * 0.75
            + genre_score * 0.15
            + author_score * 0.10
        )

        reasons = []

        if overlapping_genres:
            reasons.append(
                "Matches preferred shelves: "
                + ", ".join(
                    overlapping_genres[
                        :3
                    ]
                )
            )

        if author_score > 0:
            reasons.append(
                "You rated another book by "
                f"{candidate['author']} highly."
            )

        if not reasons:
            reasons.append(
                "Content profile is similar to your highly rated books."
            )

        ranked.append(
            {
                "title": candidate[
                    "title"
                ],
                "author": candidate[
                    "author"
                ],
                "genres": candidate[
                    "genres"
                ],
                "score": round(
                    final_score,
                    4,
                ),
                "similarity_score": round(
                    float(similarity),
                    4,
                ),
                "reasons": reasons,
            }
        )

    ranked.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    return {
        "profile_book_count": len(
            books
        ),
        "candidate_count": len(
            candidates
        ),
        "recommendations": ranked[
            :limit
        ],
    }