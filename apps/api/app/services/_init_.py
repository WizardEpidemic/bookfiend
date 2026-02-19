# Validates and stores uploaded bookshelf images for asynchronous scan processing.

import hashlib
import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.config import settings


MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 8000
SUPPORTED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


async def store_uploaded_image(image: UploadFile) -> tuple[str, str]:
    contents = await image.read()

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds the 10 MB upload limit.",
        )

    try:
        with Image.open(io.BytesIO(contents)) as parsed_image:
            image_format = parsed_image.format

            if image_format not in SUPPORTED_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Only JPEG, PNG, and WebP images are supported.",
                )

            width, height = parsed_image.size

            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Image dimensions exceed the supported limit.",
                )

            parsed_image.verify()

    except UnidentifiedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid image.",
        ) from exc

    image_hash = hashlib.sha256(contents).hexdigest()

    upload_directory = Path(settings.upload_dir)
    upload_directory.mkdir(parents=True, exist_ok=True)

    extension = SUPPORTED_FORMATS[image_format]
    storage_name = f"{uuid.uuid4()}{extension}"
    storage_path = upload_directory / storage_name

    storage_path.write_bytes(contents)

    return str(storage_path), image_hash