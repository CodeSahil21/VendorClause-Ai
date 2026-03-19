# =============================
# LEGAL RAG INGESTION PIPELINE (FULL FEATURE + NVIDIA SAFE FINAL)
# =============================

import hashlib
import asyncio
import logging
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__)
.parent.parent.parent))

from llama_parse import LlamaParse
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from fastembed import SparseTextEmbedding
from qdrant_client import AsyncQdrantClient, models

from src.shared.settings import settings
from src.shared.neo4j_service import Neo4jService
from src.shared.progress_tracker import ProgressTracker
from src.shared.langfuse_config import trace_ingestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LEGAL_RAG_PIPELINE")


class LegalRAGIngestion:

    def __init__(self):

        self.progress = ProgressTracker()

        # 🔥 NVIDIA LLM (SAFE CONFIG)
        self.llm = ChatOpenAI(
            openai_api_base="https://integrate.api.nvidia.com/v1",
            openai_api_key=settings.nvidia_api_key,
            model="meta/llama-3.1-70b-instruct",
            temperature=0,
            max_tokens=800,
            request_timeout=120,
            max_retries=0
        )

        # 🔥 GRAPH PROMPT (FULL EXTRACTION)
        self.GRAPH_PROMPT = ChatPromptTemplate.from_messages([
            ("system",
"""
Extract a COMPLETE legal knowledge graph from the given text.

Rules:
- Extract all meaningful entities. Allowed node types: Party, Clause, Obligation, Right, Payment, Service, TerminationCondition, Liability, ConfidentialInformation.
- Extract all relationships. Allowed relationship types: HAS_CLAUSE, HAS_OBLIGATION, OWES_PAYMENT, PROVIDES_SERVICE, CAN_TERMINATE, LIMITS_LIABILITY.
- Use only the allowed node and relationship types exactly as written (case-sensitive).
- Normalize entity names.
- Avoid generic words.

Return ONLY JSON.
"""
             ),
            ("human", "{input}")
        ])

        # 🔥 GRAPH TRANSFORMER
        self.graph_transformer = LLMGraphTransformer(
            llm=self.llm,
            prompt=self.GRAPH_PROMPT,
            allowed_nodes=[
                "Party", "Clause", "Obligation", "Right", "Payment",
                "Service", "TerminationCondition", "Liability", "ConfidentialInformation"
            ],
            allowed_relationships=[
                "HAS_CLAUSE", "HAS_OBLIGATION", "OWES_PAYMENT",
                "PROVIDES_SERVICE", "CAN_TERMINATE", "LIMITS_LIABILITY"
            ],
            strict_mode=True,
            node_properties=False,
            relationship_properties=False,
        )

        # 🔥 EMBEDDINGS (HYBRID)
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True, 'batch_size': 32}
        )

        self.sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

        self.qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = "legal_contracts_hybrid"

        self.neo4j = Neo4jService()

    # =================================================
    async def init_db(self):
        exists = await self.qdrant.collection_exists(self.collection_name)

        if not exists:
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
                }
            )

    # =================================================
    @trace_ingestion(name="parse_pdf")
    async def parse_pdf(self, file_path: str):

        parser = LlamaParse(
            api_key=settings.llama_cloud_api_key,
            result_type="markdown",
            parsing_instruction="Extract text exactly and preserve structure."
        )

        docs = await asyncio.to_thread(parser.load_data, file_path)
        return "\n\n".join(doc.text for doc in docs)

    # =================================================
    def split_legal_sections(self, text: str):

        pattern = re.compile(r"""
        (
            \d+\.\s+[A-Z][A-Z\s]+|
            \d+(\.\d+)*|
            §\d+|
            Section\s+\d+|
            Article\s+[IVX]+
        )
        """, re.VERBOSE | re.IGNORECASE)

        matches = list(pattern.finditer(text))

        if not matches:
            return [text]

        sections = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append(text[start:end].strip())

        return sections

    # =================================================
    def extract_clause_metadata(self, text: str):

        metadata = {}

        match = re.search(r'^(\d+(\.\d+)*)[.:\s]+(.+)', text, re.MULTILINE)
        if match:
            metadata["clause_number"] = match.group(1)
            metadata["clause_title"] = match.group(3)
            metadata["clause_path"] = match.group(1)

        if "clause_path" not in metadata:
            h = int(hashlib.sha256(text[:50].encode()).hexdigest(), 16) % 10000
            metadata["clause_path"] = f"section_{h}"

        metadata["clause_type"] = self.classify_clause(text)

        return metadata

    # =================================================
    def classify_clause(self, text):

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

    # =================================================
    @trace_ingestion(name="chunk_document")
    def chunk_document(self, text: str, document_id: str):

        sections = self.split_legal_sections(text)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=120
        )

        chunks = []

        for section in sections:

            doc = Document(page_content=section)
            doc.metadata["document_id"] = document_id

            meta = self.extract_clause_metadata(section)
            doc.metadata.update(meta)

            split_docs = splitter.split_documents([doc])

            for i, c in enumerate(split_docs):
                c.metadata["chunk_index"] = i
                chunks.append(c)

        return chunks

    # =================================================
    def filter_entities(self, nodes):

        IGNORE = {'agreement','contract'}  # 🔥 reduced

        seen = set()
        out = []

        for n in nodes:
            t = re.sub(r'[^a-z0-9 ]', '', n.id.lower())

            if len(t) < 3 or t in IGNORE:
                continue
            if t in seen:
                continue

            seen.add(t)
            n.id = t
            out.append(n)

        return out

    # =================================================
    @trace_ingestion(name="extract_graph")
    async def extract_graph(self, chunks):

        semaphore = asyncio.Semaphore(1)  # 🔥 NO BURST
        graph_docs = []

        self.last_call_time = getattr(self, "last_call_time", 0)
        self.min_interval = 22.0  # 🔥 Increased to 22s (~2.7 RPM) to avoid Strict 5000 Tokens/Minute limit

        def normalize(text):
            text = str(text).lower().strip()
            text = re.sub(r'[^a-z0-9 ]', '', text)

            mapping = {
                "service provider": "provider",
                "vendor": "provider",
                "supplier": "provider",
                "client": "customer",
                "customer": "customer"
            }
            return mapping.get(text, text)

        async def process(batch):
            async with semaphore:

                for attempt in range(5):
                    try:
                        # 🔥 GLOBAL RATE LIMIT
                        now = asyncio.get_event_loop().time()
                        wait = self.min_interval - (now - self.last_call_time)
                        if wait > 0:
                            await asyncio.sleep(wait)

                        res = await self.graph_transformer.aconvert_to_graph_documents(batch)
                        
                        logger.info(f"✅ Chunk processed via NVIDIA API successfully.")

                        self.last_call_time = asyncio.get_event_loop().time()

                        # 🔥 GRACEFULLY HANDLE EMPTY OUTPUT (e.g. Table of Contents, addresses)
                        if not res or all(not g.nodes for g in res):
                            logger.info("ℹ️ No legal entities found in this chunk. Skipping.")
                            return res

                        return res

                    except Exception as e:
                        error_str = str(e).lower()
                        if "429" in error_str or "rate" in error_str or "too many requests" in error_str:
                            backoffs = [5, 15, 30, 60, 90]
                            wait_time = backoffs[attempt] if attempt < len(backoffs) else 90
                            
                            # Clean informational log to avoid flooding the console with scary warnings
                            logger.info(f"⏳ NVIDIA Rate Limit Burst Reached. Auto-pacing for {wait_time}s...")
                        else:
                            wait_time = 1.5 * (attempt + 1)
                            logger.warning(f"Retry {attempt+1}/5: {e}, waiting {wait_time}s")
                        
                        await asyncio.sleep(wait_time)

                return []

        # Process sequentially so rate limits are tightly controlled
        results = []
        for i in range(0, len(chunks), 1):
            batch = chunks[i:i+1]
            res = await process(batch)
            results.append(res)

        for res in results:
            for g in res:
                if not g.nodes:
                    continue

                logger.info(f"RAW LLM → nodes: {len(g.nodes)}, rels: {len(g.relationships)}")

                g.nodes = self.filter_entities(g.nodes)

                for n in g.nodes:
                    n.id = normalize(n.id)

                g.nodes = g.nodes[:20]

                valid = {n.id for n in g.nodes}

                clean_rels = []
                for r in g.relationships:
                    r.source.id = normalize(r.source.id)
                    r.target.id = normalize(r.target.id)

                    # 🔥 STRICT REL FILTER: Both endpoints must exist in nodes
                    if r.source.id in valid and r.target.id in valid:
                        clean_rels.append(r)

                g.relationships = clean_rels[:30]

                # 🔥 ALLOW SMALL GRAPHS
                if g.nodes:
                    graph_docs.append(g)

        logger.info(f"✅ Extracted {len(graph_docs)} graph docs")

        return graph_docs

    # =================================================
    async def store_graph_to_neo4j(self, graph_docs, document_id):

        await self.neo4j.create_document_node(document_id, {"type": "Contract"})
        await self.neo4j.store_graph_documents(graph_docs, document_id)

    # =================================================
    async def index_chunks(self, chunks):

        BATCH_SIZE = 16  # 🔥 tune 8–32 based on CPU

        for i in range(0, len(chunks), BATCH_SIZE):

            batch = chunks[i:i+BATCH_SIZE]
            texts = [c.page_content for c in batch]

            # 🔹 Dense embeddings (batched)
            dense = await asyncio.to_thread(
                self.embedding_model.embed_documents,
                texts
            )

            # 🔹 Sparse embeddings (batched)
            sparse = await asyncio.to_thread(
                lambda: list(self.sparse_model.embed(texts))
            )

            points = []

            for j, c in enumerate(batch):

                cid = hashlib.md5(c.page_content.encode()).hexdigest()

                points.append(models.PointStruct(
                    id=int(cid, 16) % (2**63),
                    payload={"text": c.page_content, **c.metadata},
                    vector={
                        "dense": dense[j],
                        "sparse": models.SparseVector(
                            indices=sparse[j].indices.tolist(),
                            values=sparse[j].values.tolist()
                        )
                    }
                ))

            # 🔹 Upsert per batch (prevents memory spikes)
            await self.qdrant.upsert(self.collection_name, points)

            logger.info(f"✅ Indexed batch {i//BATCH_SIZE + 1}")

    # =================================================
    @trace_ingestion(name="process_document")
    async def process_document(self, file_path, document_id, job_id=None):

        await self.init_db()

        text = await self.parse_pdf(file_path)

        chunks = self.chunk_document(text, document_id)

        graph_docs = await self.extract_graph(chunks)

        await self.store_graph_to_neo4j(graph_docs, document_id)

        await self.index_chunks(chunks)

        logger.info("✅ FULL PIPELINE COMPLETE")

        return chunks

    async def close(self):
        await self.neo4j.close()