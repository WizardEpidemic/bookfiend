# Validates BookFiend's committed evaluation report against its measured regression baseline.

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

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


def _load_json(
    path: Path,
) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def main() -> int:
    baseline = _load_json(
        BASELINE_PATH
    )

    report = _load_json(
        REPORT_PATH
    )

    current = report["metrics"]

    failures: list[str] = []

    if (
        current["ocr_cer"]
        > baseline["ocr_cer"]
        + CER_TOLERANCE
    ):
        failures.append(
            "OCR CER exceeded the stored "
            "regression tolerance."
        )

    accuracy_metrics = (
        "book_top_1_accuracy",
        "book_top_3_accuracy",
        "book_top_5_accuracy",
        "end_to_end_identification_rate",
    )

    for metric_name in accuracy_metrics:
        if (
            current[metric_name]
            < baseline[metric_name]
            - ACCURACY_TOLERANCE
        ):
            failures.append(
                f"{metric_name} exceeded "
                "the stored regression tolerance."
            )

    print(
        "Committed evaluation metrics:"
    )
    print(
        f"  OCR CER: "
        f"{current['ocr_cer'] * 100:.2f}%"
    )
    print(
        f"  Top-1 accuracy: "
        f"{current['book_top_1_accuracy'] * 100:.2f}%"
    )
    print(
        f"  Top-3 accuracy: "
        f"{current['book_top_3_accuracy'] * 100:.2f}%"
    )
    print(
        f"  Top-5 accuracy: "
        f"{current['book_top_5_accuracy'] * 100:.2f}%"
    )

    if failures:
        print(
            "Regression sanity check: FAILED"
        )

        for failure in failures:
            print(
                f"- {failure}"
            )

        return 1

    print(
        "Regression sanity check: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )