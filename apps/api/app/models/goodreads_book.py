# Defines Goodreads-imported books used to build BookFiend preference profiles.

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GoodreadsBook(Base):
    __tablename__ = "goodreads_books"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
    )

    author: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )

    isbn: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    isbn13: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    my_rating: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    bookshelves: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    date_read: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    raw_row: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )