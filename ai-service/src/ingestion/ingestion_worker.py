import asyncio
import json
import logging
import os
import signal
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import boto3
from bullmq import Worker as BullMQWorker
from redis import Redis

from src.ingestion.ingestion_service import LegalRAGIngestion
from src.shared.database_service import DatabaseService
from src.shared.langfuse_config import trace_ingestion
from src.shared.settings import settings

logger = logging.getLogger(__name__)


class IngestionWorker:
    def __init__(self):
        self.redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True,
        )
        self.pipeline = LegalRAGIngestion()
        self.db = DatabaseService()

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            use_ssl=settings.minio_use_ssl,
        )

        self.bullmq_connection = {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "password": settings.redis_password,
        }

    @trace_ingestion(name="process_document_job")
    async def process_job(self, job_data: dict) -> None:
        job_id = job_data.get("jobId")
        document_id = job_data.get("documentId")
        user_id = job_data.get("userId")
        pdf_url = job_data.get("pdfUrl")

        if not all([job_id, document_id, pdf_url]):
            logger.error(f"Missing required fields: jobId={job_id}, documentId={document_id}, pdfUrl={pdf_url}")
            return

        current_status = await asyncio.to_thread(self.db.get_job_status, job_id)
        if current_status in ("COMPLETED", "IN_PROGRESS"):
            logger.warning(f"Job {job_id} already {current_status}, skipping")
            return

        logger.info(f"Starting job {job_id} for document {document_id}")

        try:
            await asyncio.to_thread(self.db.update_job_status, job_id, "IN_PROGRESS")
            await asyncio.to_thread(self.db.update_document_status, document_id, "PROCESSING")
            self._publish_status(job_id, "IN_PROGRESS", documentId=document_id)

            bucket = settings.minio_bucket
            key = pdf_url.replace(f"minio://{bucket}/", "")

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    self.s3_client.download_fileobj(bucket, key, tmp_file)
                    tmp_path = tmp_file.name

                await self.pipeline.process_document(tmp_path, document_id, job_id)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            await asyncio.to_thread(self.db.update_job_status, job_id, "COMPLETED")
            await asyncio.to_thread(self.db.update_document_status, document_id, "READY")
            self._publish_status(job_id, "COMPLETED", documentId=document_id)
            logger.info(f"Job {job_id} completed")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id} failed: {error_msg}")
            await asyncio.to_thread(self.db.update_job_status, job_id, "FAILED", error_msg)
            await asyncio.to_thread(self.db.update_document_status, document_id, "FAILED")
            self._publish_status(job_id, "FAILED", documentId=document_id, error=error_msg)
            # Not re-raised: BullMQ would retry and cause duplicate execution

    def _publish_status(self, job_id: str, status: str, **extra) -> None:
        try:
            message = {
                "jobId": job_id,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **extra,
            }
            self.redis.publish(f"job:{job_id}", json.dumps(message))
            logger.info(f"Published job:{job_id} -> {status}")

            if status == "COMPLETED":
                self.redis.publish("ingestion:complete", json.dumps({
                    "documentId": extra.get("documentId"),
                    "jobId": job_id,
                }))
                logger.info(f"Broadcasted ingestion:complete for document {extra.get('documentId')}")
        except Exception as e:
            logger.error(f"Failed to publish status: {e}")

    async def _processor(self, job, token) -> None:
        await self.process_job(job.data)

    async def run(self) -> None:
        logger.info("Ingestion worker starting")

        shutdown_event = asyncio.Event()

        def signal_handler(sig, frame):
            logger.info("Shutdown signal received")
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        worker = BullMQWorker(
            "document-ingestion",
            self._processor,
            {"connection": self.bullmq_connection},
        )

        logger.info("Ingestion worker listening for jobs")
        await shutdown_event.wait()

        logger.info("Shutting down worker")
        await worker.close()
        await self.pipeline.close()
        logger.info("Worker stopped")


async def main():
    worker = IngestionWorker()
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
