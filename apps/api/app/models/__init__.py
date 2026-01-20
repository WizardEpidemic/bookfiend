# Exposes BookFiend database models so SQLAlchemy and Alembic can discover their metadata.

from app.models.scan_job import ScanJob

__all__ = ["ScanJob"]