"""
Ingestion Worker Entry Point
Run: python ingestion_worker.py
"""
import asyncio
import logging
from src.ingestion.ingestion_worker import IngestionWorker


logger = logging.getLogger(__name__)

async def main():
    logger.info("Ingestion pipeline starting")
    worker = IngestionWorker()
    await worker.run()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
