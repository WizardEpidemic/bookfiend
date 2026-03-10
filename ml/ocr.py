# Runs RapidOCR through ONNX Runtime and converts OCR output into serializable BookFiend results.

from typing import Any

import numpy as np
from rapidocr import RapidOCR


_ocr_engine: RapidOCR | None = None


def get_ocr_engine() -> RapidOCR:
    global _ocr_engine

    if _ocr_engine is None:
        _ocr_engine = RapidOCR()

    return _ocr_engine


def run_ocr(image: np.ndarray) -> dict[str, Any]:
    engine = get_ocr_engine()

    result = engine(
        image,
        use_det=True,
        use_cls=True,
        use_rec=True,
    )

    if (
        result.boxes is None
        or result.txts is None
        or result.scores is None
    ):
        return {
            "text_regions": 0,
            "elapsed_seconds": round(float(result.elapse or 0), 4),
            "lines": [],
        }

    lines = []

    for box, text, score in zip(
        result.boxes,
        result.txts,
        result.scores,
    ):
        serialized_box = [
            [round(float(x), 2), round(float(y), 2)]
            for x, y in box
        ]

        lines.append(
            {
                "text": text,
                "confidence": round(float(score), 4),
                "box": serialized_box,
            }
        )

    return {
        "text_regions": len(lines),
        "elapsed_seconds": round(float(result.elapse or 0), 4),
        "lines": lines,
    }