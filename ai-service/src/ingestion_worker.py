import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis import Redis
from src.settings import settings
from src.ingestion_service import LegalRAGIngestion
from src.database_service import DatabaseService
import boto3
import tempfile
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IngestionWorker:
    def __init__(self):
        self.redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True
        )
        self.queue_name = "bull:document-ingestion:wait"
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
        
    async def process_job(self, job_data: dict):
        """Process a single document ingestion job"""
        job_id = job_data.get('jobId')
        document_id = job_data.get('documentId')
        user_id = job_data.get('userId')
        pdf_url = job_data.get('pdfUrl')
        
        logger.info(f"📄 Processing job {job_id} for document {document_id}")
        
        try:
            # Update job status to IN_PROGRESS
            self.db.update_job_status(job_id, "IN_PROGRESS")
            self.db.update_document_status(document_id, "PROCESSING")
            self.notify_status(job_id, "IN_PROGRESS", documentId=document_id)
            
            # Download PDF from MinIO
            bucket = settings.minio_bucket
            key = pdf_url.replace(f"minio://{bucket}/", "")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                self.s3_client.download_fileobj(bucket, key, tmp_file)
                tmp_path = tmp_file.name
            
            # Process with advanced pipeline (pass job_id)
            await self.pipeline.process_document(tmp_path, document_id, job_id)
            
            # Cleanup
            os.unlink(tmp_path)
            
            # Update job status to COMPLETED
            self.db.update_job_status(job_id, "COMPLETED")
            self.db.update_document_status(document_id, "READY")
            self.notify_status(job_id, "COMPLETED", documentId=document_id)
            
            logger.info(f"✅ Job {job_id} completed successfully")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Job {job_id} failed: {error_msg}")
            
            # Update job status to FAILED
            self.db.update_job_status(job_id, "FAILED", error=error_msg)
            self.db.update_document_status(document_id, "FAILED")
            self.notify_status(job_id, "FAILED", documentId=document_id, error=error_msg)
            
            raise
    
    def notify_status(self, job_id: str, status: str, **extra):
        """Publish job status to Redis for Socket.IO"""
        try:
            from datetime import datetime, UTC
            message = {
                'jobId': job_id,
                'status': status,
                'timestamp': datetime.now(UTC).isoformat(),
                **extra
            }
            self.redis.publish(f'job:{job_id}', json.dumps(message))
            logger.info(f"📢 Published: job:{job_id} -> {status}")
        except Exception as e:
            logger.error(f"❌ Failed to publish status: {str(e)}")
    
    async def listen(self):
        """Listen to Redis queue for new jobs"""
        logger.info("🔄 Ingestion worker started, listening for jobs...")
        
        while True:
            try:
                # Pop job from queue (blocking with 5 second timeout)
                result = self.redis.blpop(self.queue_name, timeout=5)
                
                if result:
                    queue_name, job_id = result
                    
                    # Get job data from Redis hash
                    job_key = f"bull:document-ingestion:{job_id}"
                    job_data_str = self.redis.hget(job_key, "data")
                    
                    if job_data_str:
                        job_data = json.loads(job_data_str)
                        await self.process_job(job_data)
                    
            except KeyboardInterrupt:
                logger.info("🛑 Worker stopped by user")
                break
            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
                await asyncio.sleep(5)

async def main():
    worker = IngestionWorker()
    await worker.listen()

if __name__ == "__main__":
    asyncio.run(main())
