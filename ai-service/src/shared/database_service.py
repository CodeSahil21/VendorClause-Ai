import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from src.shared.settings import settings
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.engine = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def update_job_status(self, job_id: str, status: str, error: str = None):
        """Update job status in PostgreSQL"""
        with self.SessionLocal() as session:
            try:
                if status == "IN_PROGRESS":
                    query = text("""
                        UPDATE "Job" 
                        SET status = :status, "startedAt" = :started_at
                        WHERE id = :job_id
                    """)
                    session.execute(query, {
                        "status": status,
                        "started_at": datetime.now(timezone.utc),
                        "job_id": job_id
                    })
                
                elif status == "COMPLETED":
                    query = text("""
                        UPDATE "Job" 
                        SET status = :status, "completedAt" = :completed_at
                        WHERE id = :job_id
                    """)
                    session.execute(query, {
                        "status": status,
                        "completed_at": datetime.now(timezone.utc),
                        "job_id": job_id
                    })
                
                elif status == "FAILED":
                    query = text("""
                        UPDATE "Job" 
                        SET status = :status, error = :error, "completedAt" = :completed_at
                        WHERE id = :job_id
                    """)
                    session.execute(query, {
                        "status": status,
                        "error": error,
                        "completed_at": datetime.now(timezone.utc),
                        "job_id": job_id
                    })
                
                session.commit()
                logger.info(f"✅ Job {job_id} status updated to {status}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"❌ Failed to update job status: {str(e)}")
                raise
    
    def update_document_status(self, document_id: str, status: str):
        """Update document status in PostgreSQL"""
        with self.SessionLocal() as session:
            try:
                query = text("""
                    UPDATE "Document" 
                    SET status = :status
                    WHERE id = :document_id
                """)
                session.execute(query, {
                    "status": status,
                    "document_id": document_id
                })
                session.commit()
                logger.info(f"✅ Document {document_id} status updated to {status}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"❌ Failed to update document status: {str(e)}")
                raise

    def get_job_status(self, job_id: str) -> str | None:
        """Get the current status of a job for idempotency checks"""
        with self.SessionLocal() as session:
            try:
                result = session.execute(
                    text('SELECT status FROM "Job" WHERE id = :id'),
                    {"id": job_id}
                )
                row = result.fetchone()
                return row[0] if row else None
            except Exception as e:
                logger.error(f"❌ Failed to get job status: {str(e)}")
                return None
