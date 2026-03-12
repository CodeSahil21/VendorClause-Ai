"""
Ingestion Worker Entry Point
Run: python ingestion_worker.py
"""
import asyncio
from src.ingestion.ingestion_worker import IngestionWorker

async def main():
    worker = IngestionWorker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
