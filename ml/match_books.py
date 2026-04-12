# Resolves OCR-derived book candidates against cached Open Library metadata using title similarity and author evidence.

import re
import time
from typing import Any

import requests
from rapidfuzz import fuzz

from app.services.metadata_cache import (
    cache_metadata,
    get_cached_metadata,
)


OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"

REQUEST_HEADERS = {
    "User-Agent": "BookFiend/0.1",
}

MATCH_THRESHOLD = 82.0
AUTHOR_SUPPORT_THRESHOLD = 65.0
SHORT_TITLE_AUTHOR_SUPPORT_THRESHOLD = 70.0
MAX_CANDIDATES_TO_MATCH = 30


def _clean_search_text(text: str) -> str:
    cleaned = text.replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


def _comparison_text(text: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        text.lower(),
    ).strip()


def _compact_text(text: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        text.lower(),
    )


def _build_query_variants(
    candidate_text: str,
) -> list[str]:
    cleaned = _clean_search_text(candidate_text)
    tokens = cleaned.split()

    variants = [cleaned]

    if len(tokens) >= 6:
        variants.append(" ".join(tokens[:-2]))
        variants.append(" ".join(tokens[:5]))

    elif len(tokens) == 5:
        variants.append(" ".join(tokens[:4]))

    elif len(tokens) == 4:
        variants.append(" ".join(tokens[:3]))
        variants.append(" ".join(tokens[1:]))

    elif len(tokens) == 3:
        variants.append(" ".join(tokens[:2]))
        variants.append(" ".join(tokens[1:]))

    deduplicated = []

    for variant in variants:
        if variant and variant not in deduplicated:
            deduplicated.append(variant)

    return deduplicated[:3]


def _fetch_open_library(
    search_type: str,
    query: str,
) -> tuple[list[dict[str, Any]], bool]:
    cached_documents = get_cached_metadata(
        search_type,
        query,
    )

    if cached_documents is not None:
        return cached_documents, True

    params = {
        search_type: query,
        "limit": 10 if search_type == "title" else 8,
        "fields": "key,title,author_name,isbn",
    }

    response = requests.get(
        OPEN_LIBRARY_SEARCH_URL,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=8,
    )

    response.raise_for_status()

    documents = response.json().get(
        "docs",
        [],
    )

    cache_metadata(
        search_type,
        query,
        documents,
    )

    return documents, False


def _length_similarity(
    left: str,
    right: str,
) -> float:
    left_length = max(
        len(_comparison_text(left)),
        1,
    )

    right_length = max(
        len(_comparison_text(right)),
        1,
    )

    return min(
        left_length,
        right_length,
    ) / max(
        left_length,
        right_length,
    )


def _author_support(
    document: dict[str, Any],
    ocr_lines: list[dict[str, Any]],
) -> float:
    authors = document.get(
        "author_name"
    ) or []

    if not authors:
        return 0.0

    ocr_texts = [
        _comparison_text(
            str(line.get("text") or "")
        )
        for line in ocr_lines
    ]

    ocr_texts = [
        text
        for text in ocr_texts
        if len(_compact_text(text)) >= 4
    ]

    ocr_tokens = [
        token
        for text in ocr_texts
        for token in text.split()
        if len(token) >= 3
    ]

    best_author_score = 0.0

    for author in authors:
        normalized_author = _comparison_text(
            author
        )

        author_tokens = [
            token
            for token in normalized_author.split()
            if len(token) >= 3
        ]

        token_scores = []

        for author_token in author_tokens:
            if not ocr_tokens:
                continue

            token_scores.append(
                max(
                    fuzz.ratio(
                        author_token,
                        ocr_token,
                    )
                    for ocr_token in ocr_tokens
                )
            )

        token_score = (
            sum(token_scores) / len(token_scores)
            if token_scores
            else 0.0
        )

        compact_author = _compact_text(
            author
        )

        full_name_score = 0.0

        for ocr_text in ocr_texts:
            compact_ocr = _compact_text(
                ocr_text
            )

            if len(compact_ocr) < max(
                4,
                int(
                    len(compact_author)
                    * 0.6
                ),
            ):
                continue

            if len(compact_ocr) > int(
                len(compact_author) * 1.5
            ):
                continue

            full_name_score = max(
                full_name_score,
                fuzz.ratio(
                    compact_author,
                    compact_ocr,
                ),
            )

        best_author_score = max(
            best_author_score,
            token_score,
            full_name_score,
        )

    return best_author_score


def _title_score(
    candidate_text: str,
    query_text: str,
    document: dict[str, Any],
) -> float:
    title = str(
        document.get("title") or ""
    )

    normalized_query = _comparison_text(
        query_text
    )

    normalized_title = _comparison_text(
        title
    )

    if normalized_query == normalized_title:
        return 100.0

    ratio_score = fuzz.ratio(
        query_text,
        title,
    )

    token_score = fuzz.token_set_ratio(
        query_text,
        title,
    )

    candidate_score = fuzz.token_set_ratio(
        candidate_text,
        title,
    )

    length_factor = _length_similarity(
        query_text,
        title,
    )

    adjusted_token_score = (
        token_score
        * max(
            length_factor,
            0.55,
        )
    )

    return max(
        ratio_score,
        adjusted_token_score,
        candidate_score * 0.94,
    )


def _find_best_match(
    candidate_text: str,
    query: str,
    documents: list[dict[str, Any]],
    ocr_lines: list[dict[str, Any]],
) -> tuple[
    dict[str, Any] | None,
    float,
    float,
    int,
]:
    best_document = None
    best_title_score = 0.0
    best_author_support = 0.0
    best_ranking_score = 0.0

    normalized_query = _comparison_text(
        query
    )

    exact_title_count = sum(
        1
        for document in documents
        if _comparison_text(
            str(
                document.get("title")
                or ""
            )
        )
        == normalized_query
    )

    for document in documents:
        title_score = _title_score(
            candidate_text,
            query,
            document,
        )

        author_support = _author_support(
            document,
            ocr_lines,
        )

        ranking_score = (
            title_score
            + min(
                author_support * 0.15,
                15.0,
            )
        )

        if (
            ranking_score
            > best_ranking_score
        ):
            best_ranking_score = (
                ranking_score
            )
            best_document = document
            best_title_score = (
                title_score
            )
            best_author_support = (
                author_support
            )

    return (
        best_document,
        best_title_score,
        best_author_support,
        exact_title_count,
    )


def match_book_candidates(
    candidates: list[dict[str, Any]],
    ocr_result: dict[str, Any],
) -> dict[str, Any]:
    matched_books: list[
        dict[str, Any]
    ] = []

    unmatched_candidates: list[
        dict[str, Any]
    ] = []

    seen_books: set[str] = set()

    ocr_lines = ocr_result.get(
        "lines",
        [],
    )

    cache_hits = 0
    cache_misses = 0

    for candidate in candidates[
        :MAX_CANDIDATES_TO_MATCH
    ]:
        candidate_text = candidate["text"]

        best_document = None
        best_score = 0.0
        best_author_support = 0.0
        best_exact_title_count = 0
        best_query = None

        request_failed = False

        for query in _build_query_variants(
            candidate_text
        ):
            try:
                (
                    documents,
                    cache_hit,
                ) = _fetch_open_library(
                    "title",
                    query,
                )

                if cache_hit:
                    cache_hits += 1
                else:
                    cache_misses += 1
                    time.sleep(0.2)

            except requests.RequestException:
                request_failed = True
                continue

            (
                document,
                score,
                author_support,
                exact_title_count,
            ) = _find_best_match(
                candidate_text,
                query,
                documents,
                ocr_lines,
            )

            ranking_score = (
                score
                + min(
                    author_support * 0.15,
                    15.0,
                )
            )

            current_ranking_score = (
                best_score
                + min(
                    best_author_support
                    * 0.15,
                    15.0,
                )
            )

            if (
                ranking_score
                > current_ranking_score
            ):
                best_document = document
                best_score = score
                best_author_support = (
                    author_support
                )
                best_exact_title_count = (
                    exact_title_count
                )
                best_query = query

            if (
                best_score >= 95
                and best_author_support
                >= AUTHOR_SUPPORT_THRESHOLD
            ):
                break

        if best_score < MATCH_THRESHOLD:
            try:
                (
                    documents,
                    cache_hit,
                ) = _fetch_open_library(
                    "q",
                    candidate_text,
                )

                if cache_hit:
                    cache_hits += 1
                else:
                    cache_misses += 1
                    time.sleep(0.2)

                (
                    document,
                    score,
                    author_support,
                    exact_title_count,
                ) = _find_best_match(
                    candidate_text,
                    candidate_text,
                    documents,
                    ocr_lines,
                )

                ranking_score = (
                    score
                    + min(
                        author_support
                        * 0.15,
                        15.0,
                    )
                )

                current_ranking_score = (
                    best_score
                    + min(
                        best_author_support
                        * 0.15,
                        15.0,
                    )
                )

                if (
                    ranking_score
                    > current_ranking_score
                ):
                    best_document = document
                    best_score = score
                    best_author_support = (
                        author_support
                    )
                    best_exact_title_count = (
                        exact_title_count
                    )
                    best_query = (
                        candidate_text
                    )

            except requests.RequestException:
                request_failed = True

        candidate_word_count = len(
            _comparison_text(
                candidate_text
            ).split()
        )

        ambiguous_without_author = (
            best_exact_title_count > 1
            and best_author_support
            < AUTHOR_SUPPORT_THRESHOLD
        )

        short_title_without_author = (
            candidate_word_count <= 2
            and best_author_support
            < SHORT_TITLE_AUTHOR_SUPPORT_THRESHOLD
        )

        if (
            best_document is None
            or best_score < MATCH_THRESHOLD
            or ambiguous_without_author
            or short_title_without_author
        ):
            unmatched_candidates.append(
                {
                    **candidate,
                    "metadata_request_failed": (
                        request_failed
                    ),
                    "ambiguous": (
                        ambiguous_without_author
                    ),
                    "insufficient_author_support": (
                        short_title_without_author
                    ),
                }
            )

            continue

        book_key = str(
            best_document.get("key")
            or best_document.get("title")
            or candidate_text
        )

        if book_key in seen_books:
            continue

        seen_books.add(book_key)

        authors = (
            best_document.get(
                "author_name"
            )
            or []
        )

        isbns = (
            best_document.get("isbn")
            or []
        )

        matched_books.append(
            {
                "open_library_key": (
                    best_document.get(
                        "key"
                    )
                ),
                "title": (
                    best_document.get(
                        "title"
                    )
                ),
                "author": (
                    authors[0]
                    if authors
                    else None
                ),
                "isbn": (
                    isbns[0]
                    if isbns
                    else None
                ),
                "candidate_text": (
                    candidate_text
                ),
                "ocr_confidence": round(
                    candidate[
                        "ocr_confidence"
                    ],
                    4,
                ),
                "match_score": round(
                    best_score / 100,
                    4,
                ),
                "author_support": round(
                    best_author_support
                    / 100,
                    4,
                ),
                "candidate_source": (
                    candidate["source"]
                ),
                "metadata_source": (
                    "open_library"
                ),
                "query_used": (
                    best_query
                ),
            }
        )

    return {
        "books": matched_books,
        "unmatched_candidates": (
            unmatched_candidates[:20]
        ),
        "cache": {
            "hits": cache_hits,
            "misses": cache_misses,
        },
    }