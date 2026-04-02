import asyncio
import logging

from langchain_core.documents import Document
from qdrant_client import AsyncQdrantClient, models

from src.shared.langfuse_config import update_observation

logger = logging.getLogger(__name__)


class VectorIndexer:
    def __init__(self, qdrant: AsyncQdrantClient, embedding_model, sparse_model, collection_name: str):
        self.qdrant = qdrant
        self.embedding_model = embedding_model
        self.sparse_model = sparse_model
        self.collection_name = collection_name

    async def _index_chunks(self, chunks: list[Document]) -> None:
        update_observation("index_chunks", {"chunk_count": len(chunks), "stage": "index_chunks_start"})
        batch_size = 32

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.page_content for c in batch]

            dense = await asyncio.to_thread(self.embedding_model.embed_documents, texts)
            sparse = await asyncio.to_thread(lambda t=texts: list(self.sparse_model.embed(t)))

            points = []
            for j, chunk in enumerate(batch):
                chunk_id = chunk.metadata["chunk_id"]
                points.append(models.PointStruct(
                    id=int(chunk_id, 16) % (2 ** 63),
                    payload={
                        "text": chunk.page_content,
                        "chunk_id": chunk_id,
                        "clause_type": chunk.metadata.get("clause_type"),
                        "importance": chunk.metadata.get("importance"),
                        "document_id": chunk.metadata.get("document_id"),
                        "clause_title": chunk.metadata.get("clause_title", ""),
                    },
                    vector={
                        "dense": dense[j],
                        "sparse": models.SparseVector(
                            indices=sparse[j].indices.tolist(),
                            values=sparse[j].values.tolist(),
                        ),
                    },
                ))

            await self.qdrant.upsert(self.collection_name, points)
            logger.info("Indexed vector batch %d", i // batch_size + 1)

        update_observation("index_chunks", {"stage": "index_chunks_done"})
