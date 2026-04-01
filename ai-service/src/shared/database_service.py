import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.shared.settings import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        self.engine = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def update_job_status(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        with self.SessionLocal() as session:
            try:
                result = None
                if status == "IN_PROGRESS":
                    result = session.execute(
                        text('UPDATE "Job" SET status = :status, "startedAt" = :ts WHERE id = :id'),
                        {"status": status, "ts": datetime.now(timezone.utc), "id": job_id},
                    )
                elif status == "COMPLETED":
                    result = session.execute(
                        text('UPDATE "Job" SET status = :status, "completedAt" = :ts WHERE id = :id'),
                        {"status": status, "ts": datetime.now(timezone.utc), "id": job_id},
                    )
                elif status == "FAILED":
                    result = session.execute(
                        text('UPDATE "Job" SET status = :status, error = :error, "completedAt" = :ts WHERE id = :id'),
                        {"status": status, "error": error, "ts": datetime.now(timezone.utc), "id": job_id},
                    )
                else:
                    raise ValueError(f"Unsupported job status update: {status}")

                if result.rowcount == 0:
                    raise ValueError(f"Job not found for status update: {job_id}")

                session.commit()
                logger.info(f"Job {job_id} status -> {status}")
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update job status: {e}")
                raise

    def update_document_status(self, document_id: str, status: str) -> None:
        with self.SessionLocal() as session:
            try:
                result = session.execute(
                    text('UPDATE "Document" SET status = :status WHERE id = :id'),
                    {"status": status, "id": document_id},
                )
                if result.rowcount == 0:
                    raise ValueError(f"Document not found for status update: {document_id}")

                session.commit()
                logger.info(f"Document {document_id} status -> {status}")
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update document status: {e}")
                raise

    def get_job_status(self, job_id: str) -> str | None:
        with self.SessionLocal() as session:
            try:
                result = session.execute(
                    text('SELECT status FROM "Job" WHERE id = :id'),
                    {"id": job_id},
                )
                row = result.fetchone()
                return row[0] if row else None
            except Exception as e:
                logger.error(f"Failed to get job status: {e}")
                return None
