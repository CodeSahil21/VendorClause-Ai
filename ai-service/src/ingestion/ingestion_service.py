import asyncio
import hashlib
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastembed import SparseTextEmbedding
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from llama_parse import LlamaParse
from qdrant_client import AsyncQdrantClient, models

from src.shared.langfuse_config import get_langfuse_handler, update_observation, update_trace
from src.shared.neo4j_service import Neo4jService
from src.shared.progress_tracker import ProgressTracker
from src.shared.settings import settings

logger = logging.getLogger(__name__)

GRAPH_SYSTEM_PROMPT = """
Extract a COMPLETE legal knowledge graph from the given text. Do not miss any crucial legal entity, definition, or relationship.

Rules:
- Allowed node types: Party, Clause, Obligation, Right, Payment, Service, TerminationCondition, Liability, ConfidentialInformation, Date, Jurisdiction, Definition, Regulation, Asset.
- Allowed relationship types: HAS_CLAUSE, HAS_OBLIGATION, OWES_PAYMENT, PROVIDES_SERVICE, CAN_TERMINATE, LIMITS_LIABILITY, GOVERNS, EFFECTIVE_ON, DEFINES, COMPLIES_WITH, APPLIES_TO.
- Extract node properties where applicable (e.g., specific amounts, dates, specific conditions, or exact definitions).
- Normalize entity names to be consistent (e.g., "Service Provider" -> "provider", "Client" -> "customer").
- Avoid generic words as standalone nodes.
Return ONLY valid JSON.
"""

ALLOWED_NODES = {
    "Party", "Clause", "Obligation", "Right", "Payment",
    "Service", "TerminationCondition", "Liability",
    "ConfidentialInformation", "Date", "Jurisdiction",
    "Definition", "Regulation", "Asset",
}

ALLOWED_RELATIONSHIPS = {
    "HAS_CLAUSE", "HAS_OBLIGATION", "OWES_PAYMENT",
    "PROVIDES_SERVICE", "CAN_TERMINATE", "LIMITS_LIABILITY",
    "GOVERNS", "EFFECTIVE_ON", "DEFINES", "COMPLIES_WITH", "APPLIES_TO",
}

ENTITY_ALIASES = {
    "service provider": "provider",
    "vendor": "provider",
    "supplier": "provider",
    "client": "customer",
    "customer": "customer",
    "buyer": "customer",
    "purchaser": "customer",
    "company": "company",
}

IGNORED_ENTITIES = {"agreement", "contract", "this agreement", "herein", "hereto"}

SECTION_PATTERN = re.compile(
    r"(\d+\.\s+[A-Z][A-Z\s]+|\d+(\.\d+)*|§\d+|Section\s+\d+|Article\s+[IVX]+)",
    re.VERBOSE | re.IGNORECASE,
)


class LegalRAGIngestion:
    def __init__(self):
        self.progress = ProgressTracker()

        max_concurrency = int(os.getenv("MAX_GRAPH_CONCURRENCY", "15"))
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # LLM is built WITHOUT a callback here intentionally.
        # get_langfuse_handler() must be called inside an active @observe
        # scope (process_document_job) to nest under the correct trace.
        # We attach the handler lazily in process_document() below.
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=1000,
            request_timeout=60,
            api_key=settings.openai_api_key,
        )

        self.graph_transformer = LLMGraphTransformer(
            llm=self.llm,
            prompt=ChatPromptTemplate.from_messages([
                ("system", GRAPH_SYSTEM_PROMPT),
                ("human", "{input}"),
            ]),
            allowed_nodes=list(ALLOWED_NODES),
            allowed_relationships=list(ALLOWED_RELATIONSHIPS),
            strict_mode=True,
            node_properties=True,
            relationship_properties=True,
        )

        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
        )

        self.sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        self.qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = "legal_contracts_hybrid"
        self.neo4j = Neo4jService()

        self.parser = LlamaParse(
            api_key=settings.llama_cloud_api_key,
            result_type="markdown",
            parsing_instruction="Extract text exactly and preserve legal numbering and structure.",
        )

    def _attach_langfuse_handler(self) -> None:
        """Bind a fresh CallbackHandler to self.llm.

        Called at the START of process_document() which runs inside the
        @trace_ingestion scope — so the handler is correctly nested under
        the active trace and every LLMGraphTransformer call is captured.
        """
        handler = get_langfuse_handler()
        if handler:
            self.llm.callbacks = [handler]
            logger.debug("Langfuse handler attached to LLM")

    async def init_qdrant(self) -> None:
        if not await self.qdrant.collection_exists(self.collection_name):
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
                sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            )

    async def parse_pdf(self, file_path: str) -> str:
        update_observation("parse_pdf", {"file_path": file_path, "stage": "parse_pdf_start"})
        max_retries = 3
        for attempt in range(max_retries):
            try:
                docs = await asyncio.to_thread(self.parser.load_data, file_path)
                text = "\n\n".join(doc.text for doc in docs)
                update_observation("parse_pdf", {"char_count": len(text), "stage": "parse_pdf_done"})
                return text
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "PDF Parsing failed (Attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1, max_retries, e, wait_time,
                )
                await asyncio.sleep(wait_time)

        raise RuntimeError(f"Failed to parse PDF {file_path} after {max_retries} attempts.")

    def _split_legal_sections(self, text: str) -> list[str]:
        matches = list(SECTION_PATTERN.finditer(text))
        if not matches:
            return [text]
        sections = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section = text[start:end].strip()
            if section:
                sections.append(section)
        return sections

    def _classify_clause_metadata(self, text: str) -> dict:
        t = text.lower()
        metadata = {}

        match = re.search(r"^(\d+(\.\d+)*)[.:\s]+(.+)", text, re.MULTILINE)
        if match:
            metadata["clause_number"] = match.group(1)
            metadata["clause_title"] = match.group(3)[:100]
            metadata["clause_path"] = match.group(1)
        else:
            h = int(hashlib.sha256(text[:50].encode()).hexdigest(), 16) % 10000
            metadata["clause_path"] = f"section_{h}"

        if "payment" in t or "fee" in t or "pricing" in t:
            metadata.update({"clause_type": "Payment", "importance": 3})
        elif "terminate" in t or "cancellation" in t:
            metadata.update({"clause_type": "Termination", "importance": 3})
        elif "liability" in t or "indemn" in t or "warranty" in t:
            metadata.update({"clause_type": "Liability", "importance": 3})
        elif "confidential" in t or "nda" in t or "intellectual property" in t:
            metadata.update({"clause_type": "Confidentiality", "importance": 2})
        elif "insurance" in t or "exhibit" in t or "schedule" in t or "notices" in t:
            metadata.update({"clause_type": "Administrative", "importance": 1})
        elif "define" in t or "definition" in t or "meaning" in t:
            metadata.update({"clause_type": "Definition", "importance": 2})
        else:
            metadata.update({"clause_type": "General", "importance": 1})

        return metadata

    def chunk_document(self, text: str, document_id: str) -> list[Document]:
        # Called via asyncio.to_thread — contextvars don't cross thread
        # boundaries so update_observation is a no-op here. Timing is
        # captured in process_document() and written to the trace there.
        chunks = []
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)

        for section in self._split_legal_sections(text):
            clause_meta = self._classify_clause_metadata(section)
            section_chunks = [section] if len(section) < 2000 else splitter.split_text(section)

            for i, chunk_text in enumerate(section_chunks):
                chunk_id = hashlib.sha256(
                    f"{document_id}_{clause_meta['clause_path']}_{i}_{chunk_text[:50]}".encode()
                ).hexdigest()

                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={
                        "document_id": document_id,
                        "chunk_index": i,
                        "chunk_id": chunk_id,
                        **clause_meta,
                    },
                ))

        return chunks

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
        # self.llm.callbacks is set by _attach_langfuse_handler() which is
        # called inside the active @trace_ingestion scope, so every OpenAI
        # call here is captured with tokens + cost under the correct trace.
        async with self._semaphore:
            for attempt in range(3):
                try:
                    return await self.graph_transformer.aconvert_to_graph_documents(batch)
                except Exception as e:
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

    async def process_document(self, file_path: str, document_id: str, job_id: str = None) -> list[Document]:
        # Attach the Langfuse handler NOW — we are inside the @trace_ingestion
        # scope from process_document_job, so the handler correctly nests
        # every LLM generation under the active trace.
        self._attach_langfuse_handler()

        pipeline_start = time.time()
        await self.init_qdrant()

        # ── Stage 1: Parse ────────────────────────────────────────────────────
        self.progress.update("parsing", document_id=document_id, progress=10, stage="parse_pdf")
        t0 = time.time()
        text = await self.parse_pdf(file_path)
        parse_time = time.time() - t0
        update_trace({"stage": "parsed", "char_count": len(text), "parse_time_s": round(parse_time, 2)})
        logger.info("[TIMING] PDF parsing: %.1fs (%d chars)", parse_time, len(text))

        # ── Stage 2: Chunk ────────────────────────────────────────────────────
        self.progress.update("chunking", document_id=document_id, progress=25, stage="chunk")
        t0 = time.time()
        chunks = await asyncio.to_thread(self.chunk_document, text, document_id)
        chunk_time = time.time() - t0
        update_trace({"stage": "chunked", "chunk_count": len(chunks), "chunk_time_s": round(chunk_time, 2)})
        logger.info("[TIMING] Chunking: %.1fs (%d chunks)", chunk_time, len(chunks))

        # ── Stage 3: Graph extraction + Vector indexing (parallel) ────────────
        self.progress.update("processing", document_id=document_id, progress=40, stage="parallel_extract_and_index")
        high_value_chunks = [c for c in chunks if c.metadata.get("importance", 1) >= 2] or chunks
        pruned = len(chunks) - len(high_value_chunks)

        t0 = time.time()
        graph_docs, _ = await asyncio.gather(
            asyncio.create_task(self.extract_graph(high_value_chunks)),
            asyncio.create_task(self._index_chunks(chunks)),
        )
        parallel_time = time.time() - t0
        update_trace({
            "stage": "extracted_and_indexed",
            "graph_docs_count": len(graph_docs),
            "chunks_pruned_from_graph": pruned,
            "parallel_time_s": round(parallel_time, 2),
        })
        logger.info("[TIMING] Graph + Vector (parallel): %.1fs", parallel_time)

        # ── Stage 4: Neo4j storage ────────────────────────────────────────────
        self.progress.update("neo4j_storage", document_id=document_id, progress=85, stage="store_graph")
        t0 = time.time()
        await self.neo4j.create_document_node(document_id, {"type": "Contract"})
        await self.neo4j.store_graph_documents(graph_docs, document_id)
        neo4j_time = time.time() - t0
        update_trace({"stage": "neo4j_stored", "neo4j_time_s": round(neo4j_time, 2)})
        logger.info("[TIMING] Neo4j storage: %.1fs", neo4j_time)

        # ── Done ──────────────────────────────────────────────────────────────
        self.progress.update("complete", document_id=document_id, progress=100, stage="done")
        total_time = time.time() - pipeline_start
        update_trace({
            "stage": "complete",
            "total_time_s": round(total_time, 2),
            "document_id": document_id,
            "job_id": job_id,
        })
        logger.info(
            "[TIMING] ═══ Pipeline complete for %s ═══\n"
            "  PDF Parse:    %.1fs\n"
            "  Chunking:     %.1fs (%d chunks, %d pruned from graph)\n"
            "  Graph+Vector: %.1fs\n"
            "  Neo4j Store:  %.1fs\n"
            "  ─────────────────────────\n"
            "  TOTAL:        %.1fs",
            document_id, parse_time, chunk_time, len(chunks), pruned,
            parallel_time, neo4j_time, total_time,
        )
        return chunks

    async def close(self) -> None:
        await self.neo4j.close()
