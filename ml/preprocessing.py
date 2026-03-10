# Preprocesses uploaded bookshelf images and measures basic image quality before OCR.

from pathlib import Path
from typing import Any

import cv2
import numpy as np


MAX_OCR_DIMENSION = 2200


def preprocess_image(image_path: str) -> tuple[np.ndarray, dict[str, Any]]:
    image = cv2.imread(str(Path(image_path)))

    if image is None:
        raise ValueError(f"Could not read image at {image_path}")

    original_height, original_width = image.shape[:2]
    largest_dimension = max(original_height, original_width)

    scale = min(1.0, MAX_OCR_DIMENSION / largest_dimension)

    if scale < 1.0:
        resized_width = round(original_width * scale)
        resized_height = round(original_height * scale)

        image = cv2.resize(
            image,
            (resized_width, resized_height),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    brightness = float(np.mean(gray))
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced_lightness = clahe.apply(lightness)

    processed_image = cv2.cvtColor(
        cv2.merge((enhanced_lightness, channel_a, channel_b)),
        cv2.COLOR_LAB2BGR,
    )

    processed_height, processed_width = processed_image.shape[:2]

    metrics = {
        "original_width": original_width,
        "original_height": original_height,
        "processed_width": processed_width,
        "processed_height": processed_height,
        "scale": round(scale, 4),
        "brightness": round(brightness, 2),
        "blur_variance": round(blur_variance, 2),
    }

    return processed_image, metrics