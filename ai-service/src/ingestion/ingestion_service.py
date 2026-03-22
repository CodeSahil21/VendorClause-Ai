import asyncio
import hashlib
import logging
import re
import sys
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

from src.shared.langfuse_config import get_langfuse_handler, trace_ingestion
from src.shared.neo4j_service import Neo4jService
from src.shared.progress_tracker import ProgressTracker
from src.shared.settings import settings

logger = logging.getLogger(__name__)

GRAPH_SYSTEM_PROMPT = """
Extract a COMPLETE legal knowledge graph from the given text.

Rules:
- Extract all meaningful entities. Allowed node types: Party, Clause, Obligation, Right, Payment, Service, TerminationCondition, Liability, ConfidentialInformation.
- Extract all relationships. Allowed relationship types: HAS_CLAUSE, HAS_OBLIGATION, OWES_PAYMENT, PROVIDES_SERVICE, CAN_TERMINATE, LIMITS_LIABILITY.
- Use only the allowed node and relationship types exactly as written (case-sensitive).
- Normalize entity names.
- Avoid generic words.

Return ONLY JSON.
"""

ALLOWED_NODES = [
    "Party", "Clause", "Obligation", "Right", "Payment",
    "Service", "TerminationCondition", "Liability", "ConfidentialInformation",
]

ALLOWED_RELATIONSHIPS = [
    "HAS_CLAUSE", "HAS_OBLIGATION", "OWES_PAYMENT",
    "PROVIDES_SERVICE", "CAN_TERMINATE", "LIMITS_LIABILITY",
]

ENTITY_ALIASES = {
    "service provider": "provider",
    "vendor": "provider",
    "supplier": "provider",
    "client": "customer",
    "customer": "customer",
}

IGNORED_ENTITIES = {"agreement", "contract"}

SECTION_PATTERN = re.compile(
    r"(\d+\.\s+[A-Z][A-Z\s]+|\d+(\.\d+)*|§\d+|Section\s+\d+|Article\s+[IVX]+)",
    re.VERBOSE | re.IGNORECASE,
)

# NVIDIA free tier: ~3 RPM, 5000 TPM — 22s interval keeps us safely under both limits
NVIDIA_MIN_INTERVAL = 22.0
NVIDIA_429_BACKOFFS = [30, 60, 90, 120, 180]


class LegalRAGIngestion:
    def __init__(self):
        self.progress = ProgressTracker()
        self.langfuse_handler = get_langfuse_handler()

        self.last_call_time: float = 0.0
        self._nvidia_semaphore: asyncio.Semaphore | None = None

        self.llm = ChatOpenAI(
            openai_api_base="https://integrate.api.nvidia.com/v1",
            openai_api_key=settings.nvidia_api_key,
            model="meta/llama-3.1-70b-instruct",
            temperature=0,
            max_tokens=800,
            request_timeout=120,
            max_retries=0,
        )

        self.graph_transformer = LLMGraphTransformer(
            llm=self.llm,
            prompt=ChatPromptTemplate.from_messages([
                ("system", GRAPH_SYSTEM_PROMPT),
                ("human", "{input}"),
            ]),
            allowed_nodes=ALLOWED_NODES,
            allowed_relationships=ALLOWED_RELATIONSHIPS,
            strict_mode=True,
            node_properties=False,
            relationship_properties=False,
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
            parsing_instruction="Extract text exactly and preserve structure.",
        )

    @property
    def nvidia_semaphore(self) -> asyncio.Semaphore:
        # Lazily created to ensure it belongs to the running event loop (Python 3.10+)
        if self._nvidia_semaphore is None:
            self._nvidia_semaphore = asyncio.Semaphore(1)
        return self._nvidia_semaphore

    async def init_qdrant(self) -> None:
        if not await self.qdrant.collection_exists(self.collection_name):
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
                sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            )

    @trace_ingestion(name="parse_pdf")
    async def parse_pdf(self, file_path: str) -> str:
        docs = await asyncio.to_thread(self.parser.load_data, file_path)
        return "\n\n".join(doc.text for doc in docs)

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

    def _extract_clause_metadata(self, text: str) -> dict:
        metadata = {}
        match = re.search(r"^(\d+(\.\d+)*)[.:\s]+(.+)", text, re.MULTILINE)
        if match:
            metadata["clause_number"] = match.group(1)
            metadata["clause_title"] = match.group(3)
            metadata["clause_path"] = match.group(1)
        else:
            h = int(hashlib.sha256(text[:50].encode()).hexdigest(), 16) % 10000
            metadata["clause_path"] = f"section_{h}"

        metadata["clause_type"] = self._classify_clause(text)
        return metadata

    def _classify_clause(self, text: str) -> str:
        t = text.lower()
        if "payment" in t:
            return "Payment"
        if "terminate" in t:
            return "Termination"
        if "confidential" in t:
            return "Confidentiality"
        if "liability" in t:
            return "Liability"
        return "General"

    @trace_ingestion(name="chunk_document")
    def chunk_document(self, text: str, document_id: str) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
        chunks = []

        for section in self._split_legal_sections(text):
            doc = Document(page_content=section, metadata={
                "document_id": document_id,
                **self._extract_clause_metadata(section),
            })
            for i, chunk in enumerate(splitter.split_documents([doc])):
                chunk.metadata["chunk_index"] = i
                chunks.append(chunk)

        return chunks

    def _normalize_entity(self, text: str) -> str:
        text = re.sub(r"[^a-z0-9 ]", "", str(text).lower().strip())
        return ENTITY_ALIASES.get(text, text)

    def _filter_entities(self, nodes: list) -> list:
        seen = set()
        out = []
        for node in nodes:
            normalized = re.sub(r"[^a-z0-9 ]", "", node.id.lower())
            if len(normalized) < 3 or normalized in IGNORED_ENTITIES or normalized in seen:
                continue
            seen.add(normalized)
            node.id = normalized
            out.append(node)
        return out

    async def _call_nvidia(self, batch: list) -> list:
        """Single NVIDIA API call with rate limiting and retry logic."""
        async with self.nvidia_semaphore:
            for attempt in range(5):
                try:
                    now = asyncio.get_event_loop().time()
                    wait = NVIDIA_MIN_INTERVAL - (now - self.last_call_time)
                    if wait > 0:
                        await asyncio.sleep(wait)

                    run_kwargs = {}
                    if self.langfuse_handler:
                        run_kwargs["config"] = {"callbacks": [self.langfuse_handler]}

                    result = await self.graph_transformer.aconvert_to_graph_documents(batch, **run_kwargs)
                    self.last_call_time = asyncio.get_event_loop().time()

                    if not result or all(not g.nodes for g in result):
                        logger.info("No legal entities found in chunk, skipping")
                        return result

                    return result

                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in error_str or "rate" in error_str or "too many requests" in error_str:
                        wait_time = NVIDIA_429_BACKOFFS[attempt] if attempt < len(NVIDIA_429_BACKOFFS) else 180
                        logger.info(f"NVIDIA rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/5)")
                    else:
                        wait_time = 1.5 * (attempt + 1)
                        logger.warning(f"NVIDIA call failed (attempt {attempt + 1}/5): {e}, retrying in {wait_time}s")

                    await asyncio.sleep(wait_time)

            logger.error("Chunk permanently failed after 5 retries")
            return []

    def _postprocess_graph(self, raw_results: list) -> list:
        """Normalize, filter, and cap nodes/relationships from raw LLM graph output."""
        graph_docs = []

        for res in raw_results:
            for g in res:
                if not g.nodes:
                    continue

                logger.info(f"Raw LLM output: {len(g.nodes)} nodes, {len(g.relationships)} relationships")

                g.nodes = self._filter_entities(g.nodes)
                for node in g.nodes:
                    node.id = self._normalize_entity(node.id)
                g.nodes = g.nodes[:20]

                valid_ids = {n.id for n in g.nodes}
                clean_rels = []
                for rel in g.relationships:
                    rel.source.id = self._normalize_entity(rel.source.id)
                    rel.target.id = self._normalize_entity(rel.target.id)
                    if rel.source.id in valid_ids and rel.target.id in valid_ids:
                        clean_rels.append(rel)
                g.relationships = clean_rels[:30]

                if g.nodes:
                    graph_docs.append(g)

        return graph_docs

    @trace_ingestion(name="extract_graph")
    async def extract_graph(self, chunks: list) -> list:
        raw_results = []
        failed = 0

        for chunk in chunks:
            result = await self._call_nvidia([chunk])
            if result == []:
                failed += 1
            raw_results.append(result)

        if failed:
            logger.warning(f"{failed}/{len(chunks)} chunks failed graph extraction permanently")

        graph_docs = self._postprocess_graph(raw_results)
        logger.info(f"Extracted {len(graph_docs)} graph documents")
        return graph_docs

    async def _index_chunks(self, chunks: list) -> None:
        batch_size = 16

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.page_content for c in batch]

            dense = await asyncio.to_thread(self.embedding_model.embed_documents, texts)
            sparse = await asyncio.to_thread(lambda: list(self.sparse_model.embed(texts)))

            points = []
            for j, chunk in enumerate(batch):
                cid = hashlib.sha256(chunk.page_content.encode()).hexdigest()
                points.append(models.PointStruct(
                    id=int(cid, 16) % (2 ** 63),
                    payload={"text": chunk.page_content, **chunk.metadata},
                    vector={
                        "dense": dense[j],
                        "sparse": models.SparseVector(
                            indices=sparse[j].indices.tolist(),
                            values=sparse[j].values.tolist(),
                        ),
                    },
                ))

            await self.qdrant.upsert(self.collection_name, points)
            logger.info(f"Indexed batch {i // batch_size + 1}")

    @trace_ingestion(name="process_document")
    async def process_document(self, file_path: str, document_id: str, job_id: str = None) -> list:
        await self.init_qdrant()

        self.progress.update("parsing", document_id=document_id, progress=10, stage="parse_pdf")
        text = await self.parse_pdf(file_path)

        self.progress.update("chunking", document_id=document_id, progress=30, stage="chunk")
        chunks = await asyncio.to_thread(self.chunk_document, text, document_id)

        self.progress.update("graph", document_id=document_id, progress=50, stage="extract_graph")
        graph_docs = await self.extract_graph(chunks)
        await self.neo4j.create_document_node(document_id, {"type": "Contract"})
        await self.neo4j.store_graph_documents(graph_docs, document_id)

        self.progress.update("indexing", document_id=document_id, progress=80, stage="index_chunks")
        await self._index_chunks(chunks)

        self.progress.update("complete", document_id=document_id, progress=100, stage="done")
        logger.info("Pipeline complete")
        return chunks

    async def close(self) -> None:
        await self.neo4j.close()
