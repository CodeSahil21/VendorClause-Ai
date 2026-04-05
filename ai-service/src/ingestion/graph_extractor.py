# Standard library
import asyncio
import logging
import re

# Third-party
from langchain_core.documents import Document

# Local
from src.shared.langfuse_config import update_observation
from .constants import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, ENTITY_ALIASES, IGNORED_ENTITIES

logger = logging.getLogger(__name__)


class GraphExtractor:
    def __init__(self, graph_transformer, semaphore: asyncio.Semaphore):
        self.graph_transformer = graph_transformer
        self._semaphore = semaphore

    def _normalize_entity(self, text: str) -> str:
        text = re.sub(r"[^a-z0-9 ]", "", str(text).lower().strip())
        return ENTITY_ALIASES.get(text, text)

    def _filter_entities(self, nodes: list, chunk_metadata: dict) -> list:
        seen = set()
        out = []
        for node in nodes:
            if node.type not in ALLOWED_NODES:
                continue
            normalized = re.sub(r"[^a-z0-9 ]", "", node.id.lower())
            if len(normalized) < 3 or normalized in IGNORED_ENTITIES or normalized in seen:
                continue
            seen.add(normalized)
            node.id = normalized
            if not hasattr(node, "properties") or not node.properties:
                node.properties = {}
            node.properties["chunk_id"] = chunk_metadata.get("chunk_id")
            node.properties["document_id"] = chunk_metadata.get("document_id")
            node.properties["clause_type"] = chunk_metadata.get("clause_type")
            node.properties["importance"] = chunk_metadata.get("importance")
            out.append(node)
        return out

    async def _extract_batch_graph(self, batch: list[Document]) -> list:
        # self.graph_transformer.llm.callbacks is set by _attach_langfuse_handler()
        # which is called inside the active @trace_ingestion scope, so every OpenAI
        # call here is captured with tokens + cost under the correct trace.
        async with self._semaphore:
            for attempt in range(3):
                try:
                    return await self.graph_transformer.aconvert_to_graph_documents(batch)
                except Exception as e:
                    # Check if it's a rate limit error (0005)
                    if "rate_limit" in str(e).lower() or "0005" in str(e):
                        wait_time = 30 + (attempt * 10)  # 30s, 40s, 50s for rate limits
                    else:
                        wait_time = 2 ** attempt
                    
                    logger.warning(
                        "Graph batch failed (attempt %d/3): %s. Retrying in %ds...",
                        attempt + 1, e, wait_time,
                    )
                    await asyncio.sleep(wait_time)
            logger.error("Graph extraction batch permanently failed after 3 attempts.")
            return []

    def _postprocess_graph(self, raw_results: list) -> list:
        graph_docs = []
        for result_batch in raw_results:
            for g in result_batch:
                if not g.nodes:
                    continue
                chunk_meta = g.source.metadata if g.source else {}
                g.nodes = self._filter_entities(g.nodes, chunk_meta)
                valid_ids = {n.id for n in g.nodes}
                clean_rels = []
                for rel in g.relationships:
                    if rel.type not in ALLOWED_RELATIONSHIPS:
                        continue
                    rel.source.id = self._normalize_entity(rel.source.id)
                    rel.target.id = self._normalize_entity(rel.target.id)
                    if rel.source.id in valid_ids and rel.target.id in valid_ids:
                        if not hasattr(rel, "properties") or not rel.properties:
                            rel.properties = {}
                        rel.properties["chunk_id"] = chunk_meta.get("chunk_id")
                        rel.properties["document_id"] = chunk_meta.get("document_id")
                        clean_rels.append(rel)
                g.relationships = clean_rels
                if g.nodes:
                    graph_docs.append(g)
        return graph_docs

    async def extract_graph(self, chunks: list[Document]) -> list:
        update_observation("extract_graph", {"chunk_count": len(chunks), "stage": "extract_graph_start"})
        tasks = [
            self._extract_batch_graph(chunks[i:i + 3])
            for i in range(0, len(chunks), 3)
        ]
        raw_results = await asyncio.gather(*tasks)
        graph_docs = self._postprocess_graph(raw_results)
        update_observation("extract_graph", {"graph_docs_count": len(graph_docs), "stage": "extract_graph_done"})
        logger.info("Extracted %d graph documents", len(graph_docs))
        return graph_docs
