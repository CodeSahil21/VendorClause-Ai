import os
import hashlib
import asyncio
import logging
from typing import List
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llama_parse import LlamaParse
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.documents import Document
from fastembed import SparseTextEmbedding
from qdrant_client import AsyncQdrantClient, models
from src.shared.settings import settings
from src.shared.neo4j_service import Neo4jService
from src.shared.database_service import DatabaseService
from src.shared.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LEGAL_RAG_PIPELINE")

class LegalRAGIngestion:
    def __init__(self):
        # Progress tracker for local monitoring
        self.progress = ProgressTracker()
        
        # Local LLM via Ollama (Qwen2.5-7B-Instruct)
        self.llm = OllamaLLM(
            model="qwen2.5:7b-instruct-q4_K_M",
            base_url="http://localhost:11434", 
            temperature=0,
            num_ctx=16384,  # Optimized for graph extraction
            num_predict=512,
            num_thread=8  # Use all CPU threads
        )
        
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            model_kwargs={
                'device': 'cpu',
                'trust_remote_code': True
            },
            encode_kwargs={
                'normalize_embeddings': True,
                'batch_size': 32
            },
            cache_folder="./models"
        )
        
        # Sparse embeddings (BM25-like)
        self.sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        
        # Knowledge Graph schema - improved legal structure
        self.graph_transformer = LLMGraphTransformer(
            llm=self.llm,
            allowed_nodes=[
                "Party", "Clause", "Obligation", "Right", "Payment",
                "Service", "TerminationCondition", "Liability", "ConfidentialInformation"
            ],
            allowed_relationships=[
                "HAS_CLAUSE", "HAS_OBLIGATION", "OWES_PAYMENT",
                "PROVIDES_SERVICE", "CAN_TERMINATE", "LIMITS_LIABILITY"
            ],
            strict_mode=True
        )
        
        # Qdrant async client
        self.qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = "legal_contracts_hybrid"
        
        # Neo4j service
        self.neo4j = Neo4jService()
    
    async def init_db(self):
        """Initialize Qdrant collection"""
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
            logger.info("✅ Qdrant hybrid collection created")
    
    def generate_id(self, document_id: str, clause_path: str, chunk_index: int) -> int:
        """Generate unique integer ID for Qdrant (hash-based)"""
        id_string = f"{document_id}_{clause_path}_{chunk_index}"
        # Convert to unsigned 64-bit integer using hash
        return abs(hash(id_string)) % (2**63)
    
    async def parse_pdf(self, file_path: str) -> str:
        """Parse PDF with LlamaParse - combines all pages"""
        logger.info("📄 Parsing PDF")
        self.progress.update("processing", stage="Parsing PDF", progress=10)
        
        parser = LlamaParse(
            api_key=settings.llama_cloud_api_key,
            result_type="markdown",
            parsing_instruction="""
            Extract text exactly and convert to Markdown.
            Preserve headings, tables, and clause numbering.
            """
        )
        
        docs = await asyncio.to_thread(parser.load_data, file_path)
        
        if not docs:
            raise ValueError("No text extracted")
        
        # FIX: Combine ALL pages, not just first page
        markdown = "\n\n".join(doc.text for doc in docs)
        
        if not markdown.strip():
            raise ValueError("PDF parsing returned empty text")
        
        return markdown
    
    def chunk_document(self, markdown_text: str, document_id: str) -> List[Document]:
        """Universal legal chunking with multi-pattern clause detection"""
        logger.info("🔪 Universal clause detection")
        self.progress.update("processing", document_id, stage="Chunking", progress=30)
        
        # Clean legal text and detect page breaks
        markdown_text = self.clean_legal_text(markdown_text)
        page_map = self.extract_page_breaks(markdown_text)
        
        # Split using finditer (cleaner than re.split)
        sections = self.split_legal_sections(markdown_text)
        
        # Create documents with enhanced metadata
        chunks = []
        char_position = 0
        
        for section in sections:
            if len(section) < 50:  # Skip too short
                continue
                
            doc = Document(page_content=section)
            doc.metadata["document_id"] = document_id
            doc.metadata["doc_type"] = "Legal_Contract"
            
            # Extract clause hierarchy and classify
            clause_info = self.extract_clause_metadata(section)
            doc.metadata.update(clause_info)
            
            # Map chunk to page number (before splitting)
            doc.metadata['page_number'] = self.get_page_for_position(char_position, page_map)
            doc.metadata['_original_page'] = doc.metadata['page_number']  # Preserve for child chunks
            char_position += len(section)
            
            chunks.append(doc)
        
        # Recursive split for long clauses
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=120
        )
        
        final_chunks = recursive_splitter.split_documents(chunks)
        
        # Re-extract metadata from child chunks and inherit page number
        for idx, chunk in enumerate(final_chunks):
            # Re-extract metadata from chunk text to fix mismatches
            new_meta = self.extract_clause_metadata(chunk.page_content)
            if new_meta:
                chunk.metadata.update(new_meta)
            
            chunk.metadata['chunk_index'] = idx
            
            # Ensure page_number is inherited from parent
            if '_original_page' in chunk.metadata:
                chunk.metadata['page_number'] = chunk.metadata['_original_page']
                del chunk.metadata['_original_page']
        
        logger.info(f"✅ {len(final_chunks)} chunks created")
        return final_chunks
    
    def split_legal_sections(self, text: str) -> List[str]:
        """Split text by legal section markers using finditer"""
        import re
        LEGAL_SECTION_PATTERN = r"""^(
            \d+\.\s+[A-Z][A-Z\s]+|     # 2. COMPENSATION AND PAYMENT
            \d+(\.\d+)*[.:\s]+|        # 1, 1.1, 2., 2:
            \d+\)\s+|                   # 1), 2)
            §\d+|                       # §2, §15
            Section\s+\d+|              # Section 2
            SECTION\s+\d+|              # SECTION 2
            SECTION\s+[IVX]+|           # SECTION II
            Section\s+[IVX]+|           # Section I
            Article\s+[IVX]+|           # Article I, II
            ARTICLE\s+[IVX]+|           # ARTICLE I
            ARTICLE\s+\d+|              # ARTICLE 5
            [A-Z]\.\s+|                 # A., B.
            \([a-z]\)\s+|               # (a), (b)
            \([a-z]\)\([ivx]+\)\s+|    # (a)(i), (b)(ii)
            \([ivx]+\)\s+               # (i), (ii)
        )"""
        
        pattern = re.compile(LEGAL_SECTION_PATTERN, re.MULTILINE | re.VERBOSE)
        matches = list(pattern.finditer(text))
        
        if not matches:
            return [text]
        
        sections = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            section = text[start:end].strip()
            if section:
                sections.append(section)
        
        return sections
    
    def extract_page_breaks(self, text: str) -> dict:
        """Extract page break positions from markdown"""
        import re
        page_map = {}
        # Enhanced pattern to catch various LlamaParse page formats
        pattern = r'(?:Page\s*:?|\-\-\-\s*Page)\s*(\d+)'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            page_num = int(match.group(1))
            page_map[match.start()] = page_num
        return page_map
    
    def get_page_for_position(self, position: int, page_map: dict) -> int:
        """Get page number for character position"""
        if not page_map:
            return 1
        page_positions = sorted(page_map.keys())
        for i, page_pos in enumerate(page_positions):
            if position < page_pos:
                return page_map[page_positions[i-1]] if i > 0 else 1
        return page_map[page_positions[-1]] if page_positions else 1
    
    def clean_legal_text(self, text: str) -> str:
        """Remove boilerplate from legal text"""
        import re
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'Attachment\s+[A-Z]', '', text)
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        text = re.sub(r'Exhibit\s+[A-Z]', '', text)
        return text
    
    def extract_clause_metadata(self, text: str) -> dict:
        """Extract hierarchical clause metadata with classification"""
        import re
        metadata = {}
        
        # Match various clause patterns (improved for ALL CAPS and mixed case)
        patterns = [
            (r'^\s*(\d+(\.\d+)*)[.:\s]+([A-Z][A-Z\s;,\-]{3,120})', 'numbered_caps'),
            (r'^\s*(\d+(\.\d+)*)[.:\s]+([A-Za-z][^\n]{3,120})', 'numbered'),
            (r'^§(\d+)[.:\s]+([A-Za-z][^\n]{3,120})', 'section_symbol'),
            (r'^Section\s+(\d+)[:\s]+([A-Za-z][^\n]{3,120})', 'section'),
            (r'^Article\s+([IVX]+)[:\s]+([A-Za-z][^\n]{3,120})', 'article'),
        ]
        
        for pattern, clause_type in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                if clause_type in ['numbered', 'numbered_caps']:
                    metadata['clause_number'] = match.group(1)
                    metadata['clause_title'] = match.group(3).strip()
                    metadata['clause_path'] = match.group(1)
                elif clause_type == 'section_symbol':
                    metadata['section'] = match.group(1)
                    metadata['clause_title'] = match.group(2).strip()
                    metadata['clause_path'] = f"§{match.group(1)}"
                elif clause_type == 'section':
                    metadata['section'] = match.group(1)
                    metadata['clause_title'] = match.group(2).strip()
                    metadata['clause_path'] = f"Section_{match.group(1)}"
                elif clause_type == 'article':
                    metadata['article'] = match.group(1)
                    metadata['clause_title'] = match.group(2).strip()
                    metadata['clause_path'] = f"Article_{match.group(1)}"
                break
        
        # FIX: Better fallback for clause_path using hash to prevent collisions
        if 'clause_path' not in metadata:
            if 'clause_title' in metadata:
                metadata['clause_path'] = f"{metadata['clause_title'][:20]}_{abs(hash(text[:50])) % 10000}"
            else:
                metadata['clause_path'] = f"section_{abs(hash(text[:50])) % 10000}"
        
        # Classify clause type (content-aware for vague titles)
        if 'clause_title' in metadata:
            content_preview = text[:200]  # First 200 chars for context
            metadata['clause_type'] = self.classify_clause(metadata['clause_title'], content_preview)
        
        return metadata
    
    def classify_clause(self, title: str, content: str = "") -> str:
        """Classify clause by semantic type (content-aware for vague titles)"""
        title_lower = title.lower()
        content_lower = content.lower()
        
        # Check title first
        if any(kw in title_lower for kw in ['payment', 'fee', 'compensation', 'invoice', 'pricing']):
            return 'PaymentTerm'
        elif any(kw in title_lower for kw in ['termination', 'cancel', 'expiration', 'renewal']):
            return 'Termination'
        elif any(kw in title_lower for kw in ['confidential', 'nda', 'proprietary', 'secret']):
            return 'Confidentiality'
        elif any(kw in title_lower for kw in ['indemnif', 'liability', 'damages', 'loss']):
            return 'Indemnification'
        elif any(kw in title_lower for kw in ['insurance', 'coverage', 'policy']):
            return 'Insurance'
        elif any(kw in title_lower for kw in ['intellectual property', 'ip', 'ownership', 'copyright', 'patent']):
            return 'IPOwnership'
        elif any(kw in title_lower for kw in ['dispute', 'arbitration', 'litigation', 'governing law']):
            return 'DisputeResolution'
        elif any(kw in title_lower for kw in ['warranty', 'guarantee', 'representation']):
            return 'Warranty'
        elif any(kw in title_lower for kw in ['service level', 'sla', 'uptime', 'performance']):
            return 'ServiceLevel'
        
        # For vague titles (General Terms, Miscellaneous), check content
        if any(vague in title_lower for vague in ['general', 'miscellaneous', 'additional', 'other']):
            if any(kw in content_lower for kw in ['payment', 'fee', 'invoice']):
                return 'PaymentTerm'
            elif any(kw in content_lower for kw in ['terminate', 'cancel']):
                return 'Termination'
            elif any(kw in content_lower for kw in ['confidential', 'proprietary']):
                return 'Confidentiality'
            elif any(kw in content_lower for kw in ['indemnif', 'liability']):
                return 'Indemnification'
        
        return 'General'
    
    def filter_legal_entities(self, entities: List) -> List:
        """Filter out legal boilerplate entities with normalization"""
        import re
        IGNORE_ENTITIES = {
            'agreement', 'service', 'services', 'contract', 'contracts',
            'party', 'parties', 'terms', 'conditions', 'herein', 'thereof',
            'receipt', 'sufficiency', 'consideration', 'witness', 'whereof',
            'hereby', 'hereunder', 'therein', 'thereto', 'foregoing', 'aforesaid',
            'work', 'works'
        }
        
        filtered = []
        for entity in entities:
            entity_text = entity.id.lower() if hasattr(entity, 'id') else str(entity).lower()
            # Normalize: remove punctuation and extra spaces
            entity_text = re.sub(r'[^a-z0-9 ]', '', entity_text).strip()
            if entity_text not in IGNORE_ENTITIES and len(entity_text) > 2:
                filtered.append(entity)
        
        return filtered
    
    async def extract_graph(self, chunks: List[Document]):
        """Extract knowledge graph with batching and entity filtering"""
        logger.info("🕸️  Extracting legal knowledge graph")
        self.progress.update("processing", stage="Extracting Graph", progress=50)
        
        BATCH_SIZE = 6
        graph_docs = []
        
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i+BATCH_SIZE]
            result = await self.graph_transformer.aconvert_to_graph_documents(batch)
            
            # Filter boilerplate entities and clean relationships
            for graph_doc in result:
                if hasattr(graph_doc, 'nodes'):
                    # Filter nodes
                    original_nodes = graph_doc.nodes
                    graph_doc.nodes = self.filter_legal_entities(original_nodes)
                    
                    # Get valid node IDs
                    valid_node_ids = {node.id for node in graph_doc.nodes}
                    
                    # Filter relationships referencing removed nodes
                    if hasattr(graph_doc, 'relationships'):
                        graph_doc.relationships = [
                            rel for rel in graph_doc.relationships
                            if rel.source.id in valid_node_ids and rel.target.id in valid_node_ids
                        ]
            
            graph_docs.extend(result)
            logger.info(f"✅ Processed batch {i//BATCH_SIZE + 1}/{(len(chunks)-1)//BATCH_SIZE + 1}")
        
        logger.info(f"✅ {len(graph_docs)} graph docs extracted")
        return graph_docs
    
    async def store_graph_to_neo4j(self, graph_docs, document_id: str):
        """Store graph in Neo4j"""
        logger.info("💾 Storing graph in Neo4j")
        
        # Create document node
        await self.neo4j.create_document_node(document_id, {"type": "Vendor_Service_Agreement"})
        
        # Store graph entities and relationships
        await self.neo4j.store_graph_documents(graph_docs, document_id)
        
        logger.info("✅ Graph stored in Neo4j")
    
    async def index_chunks(self, chunks: List[Document]):
        """Index with dual vectors and batching"""
        logger.info(f"🔢 Generating embeddings for {len(chunks)} chunks")
        self.progress.update("processing", stage="Generating Embeddings", progress=80)
        
        texts = [c.page_content for c in chunks]
        
        # Parallelize embedding generation
        dense_task = asyncio.to_thread(self.embedding_model.embed_documents, texts)
        sparse_task = asyncio.to_thread(lambda: list(self.sparse_model.embed(texts)))
        
        dense_vectors, sparse_vectors = await asyncio.gather(dense_task, sparse_task)
        
        points = []
        
        for i, chunk in enumerate(chunks):
            # Generate collision-free ID using clause path and index
            clause_path = chunk.metadata.get('clause_path', 'unknown')
            chunk_index = chunk.metadata.get('chunk_index', i)
            chunk_id = self.generate_id(chunk.metadata["document_id"], clause_path, chunk_index)
            
            # Add chunk hash for deduplication
            chunk.metadata["chunk_hash"] = hashlib.md5(chunk.page_content.encode()).hexdigest()
            
            sparse_vec = sparse_vectors[i]
            
            point = models.PointStruct(
                id=chunk_id,
                payload={"text": chunk.page_content, **chunk.metadata},
                vector={
                    "dense": dense_vectors[i],
                    "sparse": models.SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist()
                    )
                }
            )
            points.append(point)
        
        # Batch upload to Qdrant
        BATCH_SIZE = 64
        for i in range(0, len(points), BATCH_SIZE):
            await self.qdrant.upsert(
                collection_name=self.collection_name,
                points=points[i:i+BATCH_SIZE]
            )
            logger.info(f"✅ Uploaded batch {i//BATCH_SIZE + 1}/{(len(points)-1)//BATCH_SIZE + 1}")
        
        logger.info("✅ Indexed to Qdrant")
    
    def generate_doc_hash(self, file_path: str) -> str:
        """Generate hash for document deduplication"""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    
    async def process_document(self, file_path: str, document_id: str, job_id: str = None):
        """Full pipeline with job tracking"""
        db = DatabaseService() if job_id else None
        
        try:
            # Generate document hash for deduplication
            doc_hash = self.generate_doc_hash(file_path)
            logger.info(f"🔑 Document hash: {doc_hash}")
            
            if db and job_id:
                db.update_job_status(job_id, "IN_PROGRESS")
                db.update_document_status(document_id, "PROCESSING")
            
            await self.init_db()
            
            markdown = await self.parse_pdf(file_path)
            chunks = self.chunk_document(markdown, document_id)
            
            # Extract and store graph
            graph_docs = await self.extract_graph(chunks)
            await self.store_graph_to_neo4j(graph_docs, document_id)
            
            # Index to Qdrant
            await self.index_chunks(chunks)
            
            if db and job_id:
                db.update_document_status(document_id, "READY")
                db.update_job_status(job_id, "COMPLETED")
            
            logger.info("✅ Document ingestion complete")
            self.progress.update("completed", document_id, progress=100, stage="Done")
            return chunks
            
        except Exception as e:
            if db and job_id:
                db.update_job_status(job_id, "FAILED", str(e))
                db.update_document_status(document_id, "FAILED")
            logger.error(f"❌ Ingestion failed: {str(e)}")
            self.progress.update("failed", document_id, stage=f"Error: {str(e)}")
            raise
        finally:
            try:
                await self.neo4j.close()
            except:
                pass
