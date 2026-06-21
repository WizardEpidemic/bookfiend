# Evaluates BookFiend OCR and metadata matching against labeled shelf data and enforces regression baselines.

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from scipy.optimize import linear_sum_assignment


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"

for import_root in (REPO_ROOT, API_ROOT):
    import_root_string = str(import_root)

    if import_root_string not in sys.path:
        sys.path.insert(0, import_root_string)

os.chdir(API_ROOT)

GROUND_TRUTH_PATH = (
    REPO_ROOT
    / "eval"
    / "ground_truth"
    / "demo_shelf.json"
)

BASELINE_PATH = (
    REPO_ROOT
    / "eval"
    / "baseline_metrics.json"
)

REPORT_PATH = (
    REPO_ROOT
    / "eval"
    / "reports"
    / "latest.json"
)

CER_TOLERANCE = 0.03
ACCURACY_TOLERANCE = 0.15


def _normalize_text(text: str) -> str:
    return " ".join(
        "".join(
            character.lower()
            if character.isalnum()
            else " "
            for character in text
        ).split()
    )


def _levenshtein(
    left: list[str] | str,
    right: list[str] | str,
) -> int:
    previous = list(
        range(len(right) + 1)
    )

    for left_index, left_item in enumerate(
        left,
        start=1,
    ):
        current = [left_index]

        for right_index, right_item in enumerate(
            right,
            start=1,
        ):
            insertion = current[-1] + 1
            deletion = previous[right_index] + 1

            substitution = (
                previous[right_index - 1]
                + (left_item != right_item)
            )

            current.append(
                min(
                    insertion,
                    deletion,
                    substitution,
                )
            )

        previous = current

    return previous[-1]


def _load_json(
    path: Path,
) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as handle:
        return json.load(handle)


def _run_live_pipeline(
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    from ml.match_books import (
        match_book_candidates,
    )
    from ml.normalize import (
        build_book_candidates,
    )
    from ml.ocr import run_ocr
    from ml.preprocessing import (
        preprocess_image,
    )

    image_path = (
        REPO_ROOT
        / ground_truth["image_path"]
    )

    processed_image, image_metrics = (
        preprocess_image(
            str(image_path)
        )
    )

    ocr_result = run_ocr(
        processed_image
    )

    candidates = build_book_candidates(
        ocr_result,
        image_width=(
            image_metrics[
                "processed_width"
            ]
        ),
    )

    matching_result = (
        match_book_candidates(
            candidates,
            ocr_result,
        )
    )

    return {
        "ocr": ocr_result,
        "books": (
            matching_result["books"]
        ),
        "candidates": candidates,
        "unmatched_candidates": (
            matching_result[
                "unmatched_candidates"
            ]
        ),
        "metadata_cache": (
            matching_result["cache"]
        ),
        "image_metrics": image_metrics,
    }


def _evaluate_ocr(
    expected_regions: list[str],
    ocr_result: dict[str, Any],
) -> dict[str, Any]:
    observed_regions = [
        str(
            line.get("text")
            or ""
        )
        for line in ocr_result.get(
            "lines",
            [],
        )
        if str(
            line.get("text")
            or ""
        ).strip()
    ]

    if (
        not expected_regions
        or not observed_regions
    ):
        raise RuntimeError(
            "OCR evaluation requires "
            "labeled and observed text regions."
        )

    normalized_expected = [
        _normalize_text(text)
        for text in expected_regions
    ]

    normalized_observed = [
        _normalize_text(text)
        for text in observed_regions
    ]

    cost_matrix = [
        [
            _levenshtein(
                expected,
                observed,
            )
            for observed
            in normalized_observed
        ]
        for expected
        in normalized_expected
    ]

    (
        row_indices,
        column_indices,
    ) = linear_sum_assignment(
        cost_matrix
    )

    total_character_edits = 0
    total_characters = 0
    total_word_edits = 0
    total_words = 0

    alignments: list[
        dict[str, Any]
    ] = []

    for (
        row_index,
        column_index,
    ) in zip(
        row_indices,
        column_indices,
    ):
        expected = (
            normalized_expected[
                row_index
            ]
        )

        observed = (
            normalized_observed[
                column_index
            ]
        )

        character_edits = (
            _levenshtein(
                expected,
                observed,
            )
        )

        word_edits = (
            _levenshtein(
                expected.split(),
                observed.split(),
            )
        )

        total_character_edits += (
            character_edits
        )

        total_characters += len(
            expected
        )

        total_word_edits += (
            word_edits
        )

        total_words += len(
            expected.split()
        )

        alignments.append(
            {
                "expected": (
                    expected_regions[
                        row_index
                    ]
                ),
                "observed": (
                    observed_regions[
                        column_index
                    ]
                ),
                "character_edits": (
                    character_edits
                ),
                "word_edits": (
                    word_edits
                ),
            }
        )

    cer = (
        total_character_edits
        / max(
            total_characters,
            1,
        )
    )

    wer = (
        total_word_edits
        / max(
            total_words,
            1,
        )
    )

    return {
        "labeled_regions": (
            len(expected_regions)
        ),
        "observed_regions": (
            len(observed_regions)
        ),
        "character_edits": (
            total_character_edits
        ),
        "ground_truth_characters": (
            total_characters
        ),
        "cer": round(
            cer,
            4,
        ),
        "cer_percent": round(
            cer * 100,
            2,
        ),
        "wer": round(
            wer,
            4,
        ),
        "wer_percent": round(
            wer * 100,
            2,
        ),
        "alignments": alignments,
    }


def _rank_metadata_candidates(
    example: dict[str, Any],
    ocr_lines: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    from ml.match_books import (
        _author_support,
        _fetch_open_library,
        _title_score,
    )

    documents, cache_hit = (
        _fetch_open_library(
            "title",
            example["query"],
        )
    )

    ranked_documents: list[
        dict[str, Any]
    ] = []

    for document in documents:
        title_score = _title_score(
            example[
                "candidate_text"
            ],
            example["query"],
            document,
        )

        author_support = (
            _author_support(
                document,
                ocr_lines,
            )
        )

        ranking_score = (
            title_score
            + min(
                author_support * 0.15,
                15.0,
            )
        )

        ranked_documents.append(
            {
                "key": (
                    document.get(
                        "key"
                    )
                ),
                "title": (
                    document.get(
                        "title"
                    )
                ),
                "authors": (
                    document.get(
                        "author_name"
                    )
                    or []
                ),
                "title_score": round(
                    title_score,
                    4,
                ),
                "author_support": round(
                    author_support,
                    4,
                ),
                "ranking_score": round(
                    ranking_score,
                    4,
                ),
            }
        )

    ranked_documents.sort(
        key=lambda item: (
            item[
                "ranking_score"
            ]
        ),
        reverse=True,
    )

    expected_key = (
        example[
            "open_library_key"
        ]
    )

    rank = next(
        (
            index
            for index, document
            in enumerate(
                ranked_documents,
                start=1,
            )
            if document["key"]
            == expected_key
        ),
        None,
    )

    return {
        "title": (
            example["title"]
        ),
        "author": (
            example["author"]
        ),
        "expected_key": (
            expected_key
        ),
        "query": (
            example["query"]
        ),
        "candidate_text": (
            example[
                "candidate_text"
            ]
        ),
        "rank": rank,
        "cache_hit": cache_hit,
        "top_candidates": (
            ranked_documents[:5]
        ),
    }


def _evaluate_books(
    expected_books: list[
        dict[str, Any]
    ],
    result: dict[str, Any],
) -> dict[str, Any]:
    actual_keys = {
        str(
            book.get(
                "open_library_key"
            )
        )
        for book
        in result.get(
            "books",
            [],
        )
        if book.get(
            "open_library_key"
        )
    }

    expected_keys = {
        book[
            "open_library_key"
        ]
        for book
        in expected_books
    }

    identified_count = len(
        expected_keys
        & actual_keys
    )

    identification_rate = (
        identified_count
        / max(
            len(expected_keys),
            1,
        )
    )

    ocr_lines = (
        result.get(
            "ocr",
            {},
        ).get(
            "lines",
            [],
        )
    )

    rankings = [
        _rank_metadata_candidates(
            book,
            ocr_lines,
        )
        for book
        in expected_books
    ]

    def top_k_accuracy(
        k: int,
    ) -> float:
        correct = sum(
            1
            for ranking
            in rankings
            if (
                ranking["rank"]
                is not None
                and ranking["rank"]
                <= k
            )
        )

        return (
            correct
            / max(
                len(rankings),
                1,
            )
        )

    return {
        "labeled_books": (
            len(expected_books)
        ),
        "identified_books": (
            identified_count
        ),
        "end_to_end_identification_rate": (
            round(
                identification_rate,
                4,
            )
        ),
        "top_1_accuracy": round(
            top_k_accuracy(1),
            4,
        ),
        "top_3_accuracy": round(
            top_k_accuracy(3),
            4,
        ),
        "top_5_accuracy": round(
            top_k_accuracy(5),
            4,
        ),
        "rankings": rankings,
    }


def _metric_snapshot(
    report: dict[str, Any],
) -> dict[str, float]:
    return {
        "ocr_cer": (
            report["ocr"]["cer"]
        ),
        "book_top_1_accuracy": (
            report[
                "books"
            ][
                "top_1_accuracy"
            ]
        ),
        "book_top_3_accuracy": (
            report[
                "books"
            ][
                "top_3_accuracy"
            ]
        ),
        "book_top_5_accuracy": (
            report[
                "books"
            ][
                "top_5_accuracy"
            ]
        ),
        "end_to_end_identification_rate": (
            report[
                "books"
            ][
                "end_to_end_identification_rate"
            ]
        ),
    }


def _check_regression(
    current: dict[str, float],
    baseline: dict[str, float],
) -> list[str]:
    failures: list[str] = []

    if (
        current["ocr_cer"]
        > (
            baseline["ocr_cer"]
            + CER_TOLERANCE
        )
    ):
        failures.append(
            "OCR CER regressed beyond "
            "the allowed absolute tolerance "
            f"of {CER_TOLERANCE:.2f}."
        )

    for metric_name in (
        "book_top_1_accuracy",
        "book_top_3_accuracy",
        "book_top_5_accuracy",
        "end_to_end_identification_rate",
    ):
        if (
            current[metric_name]
            < (
                baseline[
                    metric_name
                ]
                - ACCURACY_TOLERANCE
            )
        ):
            failures.append(
                f"{metric_name} regressed "
                "beyond the allowed absolute "
                "tolerance "
                f"of {ACCURACY_TOLERANCE:.2f}."
            )

    return failures


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
        )

        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run the real local "
            "preprocessing, OCR, "
            "normalization, and matching "
            "pipeline."
        ),
    )

    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help=(
            "Save the current measured "
            "metrics as the regression "
            "baseline."
        ),
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Fail if measured metrics "
            "regress beyond the stored "
            "baseline tolerances."
        ),
    )

    args = parser.parse_args()

    ground_truth = _load_json(
        GROUND_TRUTH_PATH
    )

    if args.live:
        result = _run_live_pipeline(
            ground_truth
        )

        source = "live_pipeline"

    else:
        result = _load_json(
            REPO_ROOT
            / ground_truth[
                "fixture_result_path"
            ]
        )

        source = (
            "stored_genuine_pipeline_fixture"
        )

    report = {
        "dataset": (
            ground_truth["name"]
        ),
        "source": source,
        "ocr": _evaluate_ocr(
            ground_truth[
                "ocr_regions"
            ],
            result["ocr"],
        ),
        "books": _evaluate_books(
            ground_truth["books"],
            result,
        ),
    }

    metrics = _metric_snapshot(
        report
    )

    report["metrics"] = metrics

    _write_json(
        REPORT_PATH,
        report,
    )

    print(
        f"Dataset: "
        f"{ground_truth['name']}"
    )

    print(
        f"Source: {source}"
    )

    print(
        "OCR CER: "
        f"{report['ocr']['cer_percent']:.2f}% "
        f"({report['ocr']['character_edits']} "
        "edits / "
        f"{report['ocr']['ground_truth_characters']} "
        "labeled characters)"
    )

    print(
        "OCR WER: "
        f"{report['ocr']['wer_percent']:.2f}%"
    )

    print(
        "Book identification: "
        f"{report['books']['identified_books']}/"
        f"{report['books']['labeled_books']} "
        "("
        f"{report['books']['end_to_end_identification_rate'] * 100:.2f}%"
        ")"
    )

    print(
        "Book-match top-1 accuracy: "
        f"{report['books']['top_1_accuracy'] * 100:.2f}%"
    )

    print(
        "Book-match top-3 accuracy: "
        f"{report['books']['top_3_accuracy'] * 100:.2f}%"
    )

    print(
        "Book-match top-5 accuracy: "
        f"{report['books']['top_5_accuracy'] * 100:.2f}%"
    )

    print(
        "Report: "
        f"{REPORT_PATH.relative_to(REPO_ROOT)}"
    )

    if args.write_baseline:
        _write_json(
            BASELINE_PATH,
            metrics,
        )

        print(
            "Baseline written: "
            f"{BASELINE_PATH.relative_to(REPO_ROOT)}"
        )

    if args.check:
        if not BASELINE_PATH.exists():
            print(
                "Regression baseline is missing. "
                "Run with --write-baseline first.",
                file=sys.stderr,
            )

            return 2

        baseline = _load_json(
            BASELINE_PATH
        )

        failures = _check_regression(
            metrics,
            baseline,
        )

        if failures:
            print(
                "Regression check: FAILED"
            )

            for failure in failures:
                print(
                    f"- {failure}"
                )

            return 1

        print(
            "Regression check: PASSED"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )