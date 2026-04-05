"""Retrieval package for the legal RAG pipeline."""

from src.retrieval.state import RetrievalState
from src.retrieval.graph import build_graph, close_graph_resources

__all__ = [
    "RetrievalState",
    "build_graph",
    "close_graph_resources",
]
