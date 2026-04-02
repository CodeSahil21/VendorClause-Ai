"""
Ingestion package - Document processing and indexing
"""
from .pipeline import LegalRAGIngestion
from .worker import IngestionWorker

__all__ = ["LegalRAGIngestion", "IngestionWorker"]
