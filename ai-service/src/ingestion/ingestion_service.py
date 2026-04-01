# =============================
# 🚀 UNIVERSAL RAG INGESTION ENGINE (FINAL PRODUCTION)
# =============================

import asyncio
import hashlib
import logging
import os
import re
import sys
import time
from pathlib import Path

# Adjust path for microservice architecture
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

# Assuming these are available in your shared microservice utilities
from src.shared.langfuse_config import get_langfuse_handler, trace_ingestion
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
    "Definition", "Regulation", "Asset"
}

ALLOWED_RELATIONSHIPS = {
    "HAS_CLAUSE", "HAS_OBLIGATION", "OWES_PAYMENT",
    "PROVIDES_SERVICE", "CAN_TERMINATE", "LIMITS_LIABILITY",
    "GOVERNS", "EFFECTIVE_ON", "DEFINES", "COMPLIES_WITH", "APPLIES_TO"
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
        self.langfuse_handler = get_langfuse_handler()

        # Configurable concurrency for Kubernetes Pod scaling. 
        max_concurrency = int(os.getenv("MAX_GRAPH_CONCURRENCY", "15"))
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # GPT-4o-mini: Fast, extremely cheap, incredible structured JSON extraction
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

    async def init_qdrant(self) -> None:
        if not await self.qdrant.collection_exists(self.collection_name):
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
                sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            )

    @trace_ingestion(name="parse_pdf")
    async def parse_pdf(self, file_path: str) -> str:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                docs = await asyncio.to_thread(self.parser.load_data, file_path)
                return "\n\n".join(doc.text for doc in docs)
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"PDF Parsing failed (Attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        logger.error(f"PDF Parsing permanently failed for {file_path}")
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
        """Assign importance weights and clause types to enable MCP routing and RRF filtering."""
        t = text.lower()
        metadata = {}

        # 1. Title matching
        match = re.search(r"^(\d+(\.\d+)*)[.:\s]+(.+)", text, re.MULTILINE)
        if match:
            metadata["clause_number"] = match.group(1)
            metadata["clause_title"] = match.group(3)[:100]
            metadata["clause_path"] = match.group(1)
        else:
            h = int(hashlib.sha256(text[:50].encode()).hexdigest(), 16) % 10000
            metadata["clause_path"] = f"section_{h}"

        # 2. Smart Classification & Importance
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

    @trace_ingestion(name="chunk_document")
    def chunk_document(self, text: str, document_id: str) -> list[Document]:
        chunks = []
        standard_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)

        for section in self._split_legal_sections(text):
            clause_meta = self._classify_clause_metadata(section)
            
            if len(section) < 2000:
                section_chunks = [section] 
            else:
                section_chunks = standard_splitter.split_text(section)

            for i, chunk_text in enumerate(section_chunks):
                # 🔥 CRITICAL: Generate a deterministic chunk_id for Graph <-> Vector linking & deduplication
                chunk_id = hashlib.sha256(f"{document_id}_{clause_meta['clause_path']}_{i}_{chunk_text[:50]}".encode()).hexdigest()
                
                doc = Document(
                    page_content=chunk_text, 
                    metadata={
                        "document_id": document_id,
                        "chunk_index": i,
                        "chunk_id": chunk_id,  # The Bridge
                        **clause_meta
                    }
                )
                chunks.append(doc)

        return chunks

    def _normalize_entity(self, text: str) -> str:
        text = re.sub(r"[^a-z0-9 ]", "", str(text).lower().strip())
        return ENTITY_ALIASES.get(text, text)

    def _filter_entities(self, nodes: list, chunk_metadata: dict) -> list:
        seen = set()
        out = []
        for node in nodes:
            # 🛡️ HARD VALIDATION: Drop hallucinated node types
            if node.type not in ALLOWED_NODES:
                continue

            normalized = re.sub(r"[^a-z0-9 ]", "", node.id.lower())
            if len(normalized) < 3 or normalized in IGNORED_ENTITIES or normalized in seen:
                continue
            
            seen.add(normalized)
            node.id = normalized
            
            if not hasattr(node, "properties") or not node.properties:
                node.properties = {}
                
            # 🔥 INJECT THE BRIDGE: Link Node to exact Vector Chunk
            node.properties["chunk_id"] = chunk_metadata.get("chunk_id")
            node.properties["document_id"] = chunk_metadata.get("document_id")
            node.properties["clause_type"] = chunk_metadata.get("clause_type")
            node.properties["importance"] = chunk_metadata.get("importance")
            
            out.append(node)
        return out

    async def _extract_batch_graph(self, batch: list[Document]) -> list:
        async with self._semaphore:
            run_kwargs = {}
            if self.langfuse_handler:
                run_kwargs["config"] = {"callbacks": [self.langfuse_handler]}
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    return await self.graph_transformer.aconvert_to_graph_documents(batch, **run_kwargs)
                except Exception as e:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Graph extraction batch failed (Attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
            
            logger.error("Graph extraction batch permanently failed after 3 attempts. Data for this batch is lost.")
            return []

    def _postprocess_graph(self, raw_results: list, original_chunks: list[Document]) -> list:
        graph_docs = []
        
        for result_batch in raw_results:
            for i, g in enumerate(result_batch):
                if not g.nodes:
                    continue
                
                chunk_meta = g.source.metadata if g.source else {}

                g.nodes = self._filter_entities(g.nodes, chunk_meta)
                
                valid_ids = {n.id for n in g.nodes}
                clean_rels = []
                
                for rel in g.relationships:
                    # 🛡️ HARD VALIDATION: Drop hallucinated relationships
                    if rel.type not in ALLOWED_RELATIONSHIPS:
                        continue
                        
                    rel.source.id = self._normalize_entity(rel.source.id)
                    rel.target.id = self._normalize_entity(rel.target.id)
                    
                    if rel.source.id in valid_ids and rel.target.id in valid_ids:
                        if not hasattr(rel, "properties") or not rel.properties:
                            rel.properties = {}
                            
                        # 🔥 INJECT THE BRIDGE: Link Relationship to exact Vector Chunk
                        rel.properties["chunk_id"] = chunk_meta.get("chunk_id")
                        rel.properties["document_id"] = chunk_meta.get("document_id")
                        clean_rels.append(rel)
                
                g.relationships = clean_rels

                if g.nodes:
                    graph_docs.append(g)

        return graph_docs

    @trace_ingestion(name="extract_graph")
    async def extract_graph(self, chunks: list[Document]) -> list:
        batch_size = 3 
        tasks = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            tasks.append(self._extract_batch_graph(batch))

        raw_results = await asyncio.gather(*tasks)
        graph_docs = self._postprocess_graph(raw_results, chunks)
        
        logger.info(f"Extracted {len(graph_docs)} refined, grounded graph documents")
        return graph_docs

    @trace_ingestion(name="index_chunks")
    async def _index_chunks(self, chunks: list[Document]) -> None:
        batch_size = 32

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.page_content for c in batch]

            # Sequential to avoid CPU overload — both models share CPU cores
            dense = await asyncio.to_thread(self.embedding_model.embed_documents, texts)
            sparse = await asyncio.to_thread(lambda: list(self.sparse_model.embed(texts)))

            points = []
            for j, chunk in enumerate(batch):
                chunk_id = chunk.metadata["chunk_id"]
                
                points.append(models.PointStruct(
                    # Qdrant uses an integer ID derived deterministically from the chunk_id hash
                    id=int(chunk_id, 16) % (2 ** 63),
                    payload={
                        "text": chunk.page_content,
                        "chunk_id": chunk_id, # 🔥 THE BRIDGE is stored in the payload
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
            logger.info(f"Indexed vector batch {i // batch_size + 1}")

    @trace_ingestion(name="process_document")
    async def process_document(self, file_path: str, document_id: str, job_id: str = None) -> list[Document]:
        pipeline_start = time.time()
        await self.init_qdrant()

        # ── Stage 1: PDF Parsing ──
        self.progress.update("parsing", document_id=document_id, progress=10, stage="parse_pdf")
        t0 = time.time()
        text = await self.parse_pdf(file_path)
        parse_time = time.time() - t0
        logger.info(f"[TIMING] PDF parsing: {parse_time:.1f}s ({len(text)} chars)")

        # ── Stage 2: Chunking ──
        self.progress.update("chunking", document_id=document_id, progress=25, stage="chunk")
        t0 = time.time()
        chunks = await asyncio.to_thread(self.chunk_document, text, document_id)
        chunk_time = time.time() - t0
        logger.info(f"[TIMING] Chunking: {chunk_time:.1f}s ({len(chunks)} chunks)")

        # ── Stage 3: Parallel Graph Extraction & Vector Indexing ──
        self.progress.update("processing", document_id=document_id, progress=40, stage="parallel_extract_and_index")
        
        high_value_chunks = [c for c in chunks if c.metadata.get("importance", 1) >= 2]
        
        if not high_value_chunks:
            logger.warning(f"No high-value chunks detected for {document_id}. Falling back to full extraction.")
            high_value_chunks = chunks
        
        # PARALLEL GRAPH EXTRACTION (API-bound) & VECTOR INDEXING (CPU-bound)
        t0 = time.time()
        graph_task = asyncio.create_task(self.extract_graph(high_value_chunks))
        index_task = asyncio.create_task(self._index_chunks(chunks))

        graph_docs, _ = await asyncio.gather(graph_task, index_task)
        parallel_time = time.time() - t0
        logger.info(f"[TIMING] Graph extraction + Vector indexing (parallel): {parallel_time:.1f}s")

        # ── Stage 4: Neo4j Storage ──
        self.progress.update("neo4j_storage", document_id=document_id, progress=85, stage="store_graph")
        t0 = time.time()
        await self.neo4j.create_document_node(document_id, {"type": "Contract"})
        await self.neo4j.store_graph_documents(graph_docs, document_id)
        neo4j_time = time.time() - t0
        logger.info(f"[TIMING] Neo4j storage: {neo4j_time:.1f}s")

        # ── Complete ──
        self.progress.update("complete", document_id=document_id, progress=100, stage="done")
        
        total_time = time.time() - pipeline_start
        pruned_count = len(chunks) - len(high_value_chunks)
        logger.info(
            f"[TIMING] ═══ Pipeline complete for {document_id} ═══\n"
            f"  PDF Parse:    {parse_time:.1f}s\n"
            f"  Chunking:     {chunk_time:.1f}s ({len(chunks)} chunks, {pruned_count} pruned from graph)\n"
            f"  Graph+Vector: {parallel_time:.1f}s\n"
            f"  Neo4j Store:  {neo4j_time:.1f}s\n"
            f"  ─────────────────────────\n"
            f"  TOTAL:        {total_time:.1f}s"
        )
        return chunks

    async def close(self) -> None:
        await self.neo4j.close()
