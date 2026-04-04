# Standard library
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

# Third-party
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Local
from src.shared.settings import settings

logger = logging.getLogger(__name__)

_ENGINE = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
_SESSION_LOCAL = sessionmaker(bind=_ENGINE)


class DatabaseService:
    def __init__(self):
        # Reuse one SQLAlchemy engine/pool per process.
        self.SessionLocal = _SESSION_LOCAL

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
                    text('UPDATE "Document" SET status = :status, "updatedAt" = :ts WHERE id = :id'),
                    {"status": status, "ts": datetime.now(timezone.utc), "id": document_id},
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

    def get_chat_history(self, session_id: str, limit: int = 20) -> list[dict]:
        with self.SessionLocal() as session:
            try:
                result = session.execute(
                    text(
                        'SELECT role, content, "createdAt" '
                        'FROM "Message" '
                        'WHERE "sessionId" = :session_id '
                        'ORDER BY "createdAt" DESC '
                        'LIMIT :limit'
                    ),
                    {"session_id": session_id, "limit": limit},
                )
                rows = result.fetchall()
                history = [
                    {
                        "role": str(row[0]).upper(),
                        "content": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                    }
                    for row in reversed(rows)
                ]
                return history
            except Exception as e:
                logger.error(f"Failed to get chat history for session {session_id}: {e}")
                return []

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens_used: Optional[int] = None,
    ) -> None:
        role_upper = role.upper()
        if role_upper not in ("USER", "AI", "SYSTEM"):
            raise ValueError(f"Invalid role: {role}")

        with self.SessionLocal() as session:
            try:
                session.execute(
                    text(
                        'INSERT INTO "Message" (id, "sessionId", role, content, "tokensUsed", "createdAt") '
                        'VALUES (:id, :session_id, :role, :content, :tokens_used, :created_at)'
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "role": role_upper,
                        "content": content,
                        "tokens_used": tokens_used,
                        "created_at": datetime.now(timezone.utc),
                    },
                )
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to save message for session {session_id}: {e}")
                raise


_DB_SERVICE_SINGLETON: DatabaseService | None = None
_DB_SERVICE_LOCK = threading.Lock()


def get_database_service() -> DatabaseService:
    global _DB_SERVICE_SINGLETON
    if _DB_SERVICE_SINGLETON is not None:
        return _DB_SERVICE_SINGLETON

    with _DB_SERVICE_LOCK:
        if _DB_SERVICE_SINGLETON is None:
            _DB_SERVICE_SINGLETON = DatabaseService()
    return _DB_SERVICE_SINGLETON
