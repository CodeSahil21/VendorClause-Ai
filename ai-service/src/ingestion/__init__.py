"""
Ingestion package - Document processing and indexing
"""
from .ingestion_service import LegalRAGIngestion
from .ingestion_worker import IngestionWorker

__all__ = ['LegalRAGIngestion', 'IngestionWorker']
