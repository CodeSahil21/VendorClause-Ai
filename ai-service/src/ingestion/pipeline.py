# Standard library
import asyncio
import logging
import os
import time

# Third-party
from fastembed import SparseTextEmbedding
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from llama_parse import LlamaParse
from qdrant_client import AsyncQdrantClient, models

# Local
from src.shared.langfuse_config import get_langfuse_handler, update_observation, update_trace
from src.shared.neo4j_service import Neo4jService
from src.shared.progress_tracker import ProgressTracker
from src.shared.progress_events import publish_job_progress
from src.shared.redis_client import get_shared_redis
from src.shared.settings import settings
from .chunker import DocumentChunker
from .constants import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, GRAPH_SYSTEM_PROMPT
from .graph_extractor import GraphExtractor
from .vector_indexer import VectorIndexer

logger = logging.getLogger(__name__)


class LegalRAGIngestion:
    def __init__(self):
        self.progress = ProgressTracker()

        max_concurrency = int(os.getenv("MAX_GRAPH_CONCURRENCY", "5"))
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # LLM is built WITHOUT a callback here intentionally.
        # get_langfuse_handler() must be called inside an active @observe
        # scope (process_document_job) to nest under the correct trace.
        # We attach the handler lazily in process_document() below.
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=2048,
            request_timeout=120,  # Increased timeout
            max_retries=3,  # Built-in OpenAI client retries
            api_key=settings.openai_api_key,
        )

        graph_transformer = LLMGraphTransformer(
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

        embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
        )

        sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = settings.qdrant_collection_name
        self.neo4j = Neo4jService()

        self.parser = LlamaParse(
            api_key=settings.llama_cloud_api_key,
            result_type="markdown",
            parsing_instruction="Extract text exactly and preserve legal numbering and structure.",
        )

        self._chunker = DocumentChunker()
        self._graph_extractor = GraphExtractor(graph_transformer, self._semaphore)
        self._vector_indexer = VectorIndexer(qdrant, embedding_model, sparse_model, self.collection_name)

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
        qdrant = self._vector_indexer.qdrant
        if not await qdrant.collection_exists(self.collection_name):
            await qdrant.create_collection(
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

    def chunk_document(self, text: str, document_id: str) -> list[Document]:
        return self._chunker.chunk_document(text, document_id)

    async def extract_graph(self, chunks: list[Document]) -> list:
        return await self._graph_extractor.extract_graph(chunks)

    async def process_document(self, file_path: str, document_id: str, job_id: str = None) -> list[Document]:
        # Attach the Langfuse handler NOW — we are inside the @trace_ingestion
        # scope from process_document_job, so the handler correctly nests
        # every LLM generation under the active trace.
        self._attach_langfuse_handler()

        pipeline_start = time.time()
        await self.init_qdrant()
        redis_client = await get_shared_redis()

        # ── Stage 1: Parse ────────────────────────────────────────────────────
        self.progress.update("parsing", document_id=document_id, progress=10, stage="parse_pdf")
        try:
            await publish_job_progress(redis_client, job_id, document_id, "IN_PROGRESS", 10, "parse_pdf")
        except Exception:
            logger.warning("Failed to publish job progress for %s", job_id, exc_info=True)
        t0 = time.time()
        text = await self.parse_pdf(file_path)
        parse_time = time.time() - t0
        update_trace({"stage": "parsed", "char_count": len(text), "parse_time_s": round(parse_time, 2)})
        logger.info("[TIMING] PDF parsing: %.1fs (%d chars)", parse_time, len(text))

        # ── Stage 2: Chunk ────────────────────────────────────────────────────
        self.progress.update("chunking", document_id=document_id, progress=25, stage="chunk")
        try:
            await publish_job_progress(redis_client, job_id, document_id, "IN_PROGRESS", 25, "chunk")
        except Exception:
            logger.warning("Failed to publish job progress for %s", job_id, exc_info=True)
        t0 = time.time()
        chunks = await asyncio.to_thread(self.chunk_document, text, document_id)
        chunk_time = time.time() - t0
        update_trace({"stage": "chunked", "chunk_count": len(chunks), "chunk_time_s": round(chunk_time, 2)})
        logger.info("[TIMING] Chunking: %.1fs (%d chunks)", chunk_time, len(chunks))

        # ── Stage 3: Graph extraction + Vector indexing (parallel) ────────────
        self.progress.update("processing", document_id=document_id, progress=40, stage="parallel_extract_and_index")
        try:
            await publish_job_progress(redis_client, job_id, document_id, "IN_PROGRESS", 40, "parallel_extract_and_index")
        except Exception:
            logger.warning("Failed to publish job progress for %s", job_id, exc_info=True)
        high_value_chunks = [c for c in chunks if c.metadata.get("importance", 1) >= 2] or chunks
        pruned = len(chunks) - len(high_value_chunks)

        t0 = time.time()
        graph_docs, _ = await asyncio.gather(
            self.extract_graph(high_value_chunks),
            self._vector_indexer._index_chunks(chunks),
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
        try:
            await publish_job_progress(redis_client, job_id, document_id, "IN_PROGRESS", 85, "store_graph")
        except Exception:
            logger.warning("Failed to publish job progress for %s", job_id, exc_info=True)
        t0 = time.time()
        await self.neo4j.create_document_node(document_id, {"type": "Contract"})
        await self.neo4j.store_graph_documents(graph_docs, document_id)
        neo4j_time = time.time() - t0
        update_trace({"stage": "neo4j_stored", "neo4j_time_s": round(neo4j_time, 2)})
        logger.info("[TIMING] Neo4j storage: %.1fs", neo4j_time)

        # ── Done ──────────────────────────────────────────────────────────────
        self.progress.update("complete", document_id=document_id, progress=100, stage="done")
        try:
            await publish_job_progress(redis_client, job_id, document_id, "IN_PROGRESS", 99, "finalizing")
        except Exception:
            logger.warning("Failed to publish job progress for %s", job_id, exc_info=True)
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
