# Normalizes OCR text and groups spatially related OCR regions into prioritized book candidates.

import math
import re
from typing import Any


SOURCE_PRIORITY = {
    "single_region": 30,
    "vertical_group": 18,
    "vertical_group_reversed": 10,
}


def normalize_text(text: str) -> str:
    cleaned = text.strip()

    cleaned = cleaned.replace("—", " ")
    cleaned = cleaned.replace("–", " ")

    cleaned = re.sub(
        r"[^A-Za-z0-9'&:,\- ]+",
        " ",
        cleaned,
    )

    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


def _distance(
    point_a: list[float],
    point_b: list[float],
) -> float:
    return math.dist(point_a, point_b)


def _line_geometry(line: dict[str, Any]) -> dict[str, float]:
    box = line["box"]

    top_left = box[0]
    top_right = box[1]
    bottom_right = box[2]
    bottom_left = box[3]

    width = (
        _distance(top_left, top_right)
        + _distance(bottom_left, bottom_right)
    ) / 2

    height = (
        _distance(top_right, bottom_right)
        + _distance(top_left, bottom_left)
    ) / 2

    center_x = sum(point[0] for point in box) / 4
    center_y = sum(point[1] for point in box) / 4

    return {
        "width": width,
        "height": height,
        "center_x": center_x,
        "center_y": center_y,
    }


def _candidate_priority(candidate: dict[str, Any]) -> float:
    text = candidate["text"]
    words = text.split()
    text_length = len(text)

    source_bonus = SOURCE_PRIORITY.get(
        candidate["source"],
        0,
    )

    length_bonus = 0

    if 5 <= text_length <= 55:
        length_bonus = 12
    elif text_length <= 80:
        length_bonus = 5

    # Single OCR words are often author names or fragments rather than titles.
    single_word_penalty = 22 if len(words) == 1 else 0

    return (
        candidate["ocr_confidence"] * 100
        + source_bonus
        + length_bonus
        - single_word_penalty
    )


def build_book_candidates(
    ocr_result: dict[str, Any],
    image_width: int,
    max_candidates: int = 45,
) -> list[dict[str, Any]]:
    prepared_lines = []

    for line in ocr_result.get("lines", []):
        text = normalize_text(line["text"])

        if len(text) < 3:
            continue

        confidence = float(line["confidence"])

        if confidence < 0.45:
            continue

        geometry = _line_geometry(line)

        prepared_lines.append(
            {
                "text": text,
                "confidence": confidence,
                **geometry,
            }
        )

    candidates: list[dict[str, Any]] = []

    for line in prepared_lines:
        candidates.append(
            {
                "text": line["text"],
                "ocr_confidence": line["confidence"],
                "source": "single_region",
            }
        )

    vertical_lines = [
        line
        for line in prepared_lines
        if line["height"] > line["width"] * 1.15
    ]

    vertical_lines.sort(
        key=lambda line: (
            line["center_x"],
            line["center_y"],
        )
    )

    x_threshold = max(
        25.0,
        image_width * 0.025,
    )

    clusters: list[list[dict[str, Any]]] = []

    for line in vertical_lines:
        best_cluster = None

        for cluster in clusters:
            average_x = sum(
                item["center_x"]
                for item in cluster
            ) / len(cluster)

            nearest_y = min(
                abs(
                    line["center_y"]
                    - item["center_y"]
                )
                for item in cluster
            )

            if (
                abs(line["center_x"] - average_x)
                <= x_threshold
                and nearest_y <= 260
            ):
                best_cluster = cluster
                break

        if best_cluster is None:
            clusters.append([line])
        else:
            best_cluster.append(line)

    for cluster in clusters:
        if len(cluster) < 2:
            continue

        cluster.sort(
            key=lambda line: line["center_y"]
        )

        average_confidence = sum(
            line["confidence"]
            for line in cluster
        ) / len(cluster)

        forward_text = normalize_text(
            " ".join(
                line["text"]
                for line in cluster
            )
        )

        reverse_text = normalize_text(
            " ".join(
                line["text"]
                for line in reversed(cluster)
            )
        )

        candidates.append(
            {
                "text": forward_text,
                "ocr_confidence": average_confidence,
                "source": "vertical_group",
            }
        )

        if reverse_text != forward_text:
            candidates.append(
                {
                    "text": reverse_text,
                    "ocr_confidence": average_confidence,
                    "source": "vertical_group_reversed",
                }
            )

    deduplicated: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        key = candidate["text"].lower()

        existing = deduplicated.get(key)

        if (
            existing is None
            or _candidate_priority(candidate)
            > _candidate_priority(existing)
        ):
            deduplicated[key] = candidate

    ranked = sorted(
        deduplicated.values(),
        key=_candidate_priority,
        reverse=True,
    )

    return ranked[:max_candidates]