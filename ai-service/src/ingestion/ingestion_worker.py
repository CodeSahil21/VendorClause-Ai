import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bullmq import Worker as BullMQWorker
from redis import Redis
from src.shared.settings import settings
from src.ingestion.ingestion_service import LegalRAGIngestion
from src.shared.database_service import DatabaseService
from src.shared.langfuse_config import trace_ingestion
import boto3
import tempfile
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IngestionWorker:
    def __init__(self):
        # Raw redis client for pub/sub notifications only
        self.redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True
        )
        self.pipeline = LegalRAGIngestion()
        self.db = DatabaseService()

        # MinIO client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            use_ssl=settings.minio_use_ssl
        )

        # BullMQ connection config (dict form)
        self.bullmq_connection = {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "password": settings.redis_password,
        }

    @trace_ingestion(name="process_document_job")
    async def process_job(self, job_data: dict):
        """Process a single document ingestion job"""
        job_id = job_data.get('jobId')
        document_id = job_data.get('documentId')
        user_id = job_data.get('userId')
        pdf_url = job_data.get('pdfUrl')

        # Validate required fields
        if not all([job_id, document_id, pdf_url]):
            logger.error(f"Missing required job data fields: jobId={job_id}, documentId={document_id}, pdfUrl={pdf_url}")
            return

        logger.info(f"Processing job {job_id} for document {document_id}")

        try:
            # Update job status to IN_PROGRESS
            self.db.update_job_status(job_id, "IN_PROGRESS")
            self.db.update_document_status(document_id, "PROCESSING")
            self.notify_status(job_id, "IN_PROGRESS", documentId=document_id)

            # Download PDF from MinIO
            bucket = settings.minio_bucket
            key = pdf_url.replace(f"minio://{bucket}/", "")

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    self.s3_client.download_fileobj(bucket, key, tmp_file)
                    tmp_path = tmp_file.name

                # Process with advanced pipeline (pass job_id)
                await self.pipeline.process_document(tmp_path, document_id, job_id)
            finally:
                # Always clean up temp file, even on crash
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # Update job status to COMPLETED
            self.db.update_job_status(job_id, "COMPLETED")
            self.db.update_document_status(document_id, "READY")
            self.notify_status(job_id, "COMPLETED", documentId=document_id)

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id} failed: {error_msg}")

            # Update job status to FAILED
            self.db.update_job_status(job_id, "FAILED", error=error_msg)
            self.db.update_document_status(document_id, "FAILED")
            self.notify_status(job_id, "FAILED", documentId=document_id, error=error_msg)

            raise

    def notify_status(self, job_id: str, status: str, **extra):
        """Publish job status to Redis for Socket.IO"""
        try:
            from datetime import datetime, timezone
            message = {
                'jobId': job_id,
                'status': status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **extra
            }
            self.redis.publish(f'job:{job_id}', json.dumps(message))
            logger.info(f"Published: job:{job_id} -> {status}")

            # Broadcast ingestion:complete event when done
            if status == 'COMPLETED':
                complete_msg = {
                    'documentId': extra.get('documentId'),
                    'jobId': job_id
                }
                self.redis.publish('ingestion:complete', json.dumps(complete_msg))
                logger.info(f"Broadcasted: ingestion:complete for document {extra.get('documentId')}")
        except Exception as e:
            logger.error(f"Failed to publish status: {str(e)}")

    async def _processor(self, job, token):
        """BullMQ processor callback - bridges to process_job"""
        await self.process_job(job.data)

    async def run(self):
        """Start the BullMQ worker"""
        logger.info("Ingestion worker starting...")

        shutdown_event = asyncio.Event()

        def signal_handler(sig, frame):
            logger.info("Shutdown signal received, stopping worker...")
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        worker = BullMQWorker(
            "document-ingestion",
            self._processor,
            {"connection": self.bullmq_connection}
        )

        logger.info("Ingestion worker started, listening for jobs...")

        await shutdown_event.wait()

        logger.info("Closing worker...")
        await worker.close()
        logger.info("Worker stopped")

async def main():
    worker = IngestionWorker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
