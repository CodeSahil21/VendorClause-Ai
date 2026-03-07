# PolyGot System Architecture Diagram

## Complete CQRS Document Upload & Query Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER LAYER                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ HTTP/REST
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          NEXT.JS CLIENT (Port 3000)                                 │
│                                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Auth UI    │  │  Chat UI     │  │  Upload UI   │  │  Session UI  │          │
│  │  /login      │  │  /chat/[id]  │  │  Drag & Drop │  │  Sidebar     │          │
│  │  /register   │  │  Messages    │  │  Progress    │  │  List        │          │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                                     │
│  State: Zustand | API: Axios | Auth: JWT Cookies                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ HTTP/REST + JWT Cookie
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                      NODE.JS GATEWAY (Port 4000)                                    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            MIDDLEWARE LAYER                                  │   │
│  │  [Helmet] → [CORS] → [JWT Auth] → [Rate Limit] → [Validation] → [Multer]   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Auth Routes  │  │Session Routes│  │Document Routes│  │  AI Proxy    │          │
│  │              │  │              │  │               │  │              │          │
│  │ POST /login  │  │ GET /sessions│  │ POST /upload  │  │ POST /query  │          │
│  │ POST /signup │  │ POST /create │  │ GET /:id      │  │ GET /stream  │          │
│  │ POST /logout │  │ DELETE /:id  │  │ DELETE /:id   │  │              │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘  └──────┬───────┘          │
│         │                 │                 │                  │                   │
│         └─────────────────┴─────────────────┴──────────────────┘                   │
│                                     │                                               │
│                    ┌────────────────┼────────────────┐                             │
│                    ▼                ▼                ▼                             │
│         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│         │Auth Service  │  │Session Svc   │  │Document Svc  │                      │
│         │- Hash pwd    │  │- CRUD ops    │  │- Upload      │                      │
│         │- Gen JWT     │  │- Cache       │  │- Queue job   │                      │
│         │- Verify      │  │              │  │- Track status│                      │
│         └──────────────┘  └──────────────┘  └──────┬───────┘                      │
│                                                     │                               │
└─────────────────────────────────────────────────────┼───────────────────────────────┘
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────────┐
                    │                                 │                             │
                    ▼                                 ▼                             ▼
┌─────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────┐
│      POSTGRESQL              │  │         REDIS                │  │      MINIO       │
│      (Port 5432)             │  │      (Port 6379)             │  │   (Port 9000)    │
│                              │  │                              │  │                  │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │  │  ┌────────────┐  │
│  │ User                   │  │  │  │ Session Cache          │  │  │  │ documents/ │  │
│  │ - id, email, password  │  │  │  │ auth:session:{jti}     │  │  │  │  user1/    │  │
│  │ - name, createdAt      │  │  │  │                        │  │  │  │    sess1/  │  │
│  └────────────────────────┘  │  │  │ Rate Limit             │  │  │  │      doc.pdf│
│                              │  │  │ rate:{userId}          │  │  │  └────────────┘  │
│  ┌────────────────────────┐  │  │  │                        │  │  │                  │
│  │ ChatSession            │  │  │  │ BullMQ Queue           │  │  │  S3-Compatible   │
│  │ - id, userId, title    │  │  │  │ bull:document-ingestion│  │  │  Object Storage  │
│  │ - createdAt, updatedAt │  │  │  │ {                      │  │  │                  │
│  └────────────────────────┘  │  │  │   jobId,               │  │  │  Stores PDFs     │
│                              │  │  │   documentId,          │  │  │  before processing│
│  ┌────────────────────────┐  │  │  │   userId,              │  │  │                  │
│  │ Document               │  │  │  │   pdfUrl               │  │  │                  │
│  │ - id, sessionId        │  │  │  │ }                      │  │  │                  │
│  │ - fileName, s3Url      │  │  │  └────────────────────────┘  │  │                  │
│  │ - status (PENDING)     │  │  │                              │  │                  │
│  └────────────────────────┘  │  │  Single Source of Truth      │  │                  │
│                              │  │  for Queues & Cache          │  │                  │
│  ┌────────────────────────┐  │  └──────────────────────────────┘  └──────────────────┘
│  │ Job                    │  │
│  │ - id, documentId       │  │
│  │ - taskType, status     │  │
│  │ - QUEUED → IN_PROGRESS │  │
│  │   → COMPLETED/FAILED   │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │ Message                │  │
│  │ - id, sessionId        │  │
│  │ - role, content        │  │
│  │ - tokensUsed, createdAt│  │
│  └────────────────────────┘  │
│                              │
│  Prisma ORM                  │
│  Type-safe queries           │
└──────────────────────────────┘
                    │
                    │ BullMQ Worker polls Redis Queue
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    PYTHON AI SERVICE (Port 8000)                                    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         BACKGROUND WORKER                                    │   │
│  │                                                                              │   │
│  │  while True:                                                                 │   │
│  │    job = redis.pop('bull:document-ingestion')                                │   │
│  │    if job:                                                                   │   │
│  │      process_document(job.data)                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                               │
│                                     ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      INGESTION SERVICE                                       │   │
│  │                                                                              │   │
│  │  Step 1: Update Job Status                                                  │   │
│  │    postgres.update(job_id, status='IN_PROGRESS')                            │   │
│  │                                                                              │   │
│  │  Step 2: Download PDF                                                       │   │
│  │    pdf_bytes = minio.get_object(s3_url)                                     │   │
│  │                                                                              │   │
│  │  Step 3: Parse with LlamaParse                                              │   │
│  │    parsed_text = llama_parse.parse(pdf_bytes)                               │   │
│  │                                                                              │   │
│  │  Step 4: Semantic Chunking                                                  │   │
│  │    chunks = semantic_chunker.chunk(parsed_text, size=500, overlap=50)       │   │
│  │                                                                              │   │
│  │  Step 5: Generate Embeddings                                                │   │
│  │    embeddings = openai.embed(chunks, model='text-embedding-3-small')        │   │
│  │                                                                              │   │
│  │  Step 6: Store in Qdrant                                                    │   │
│  │    qdrant.upsert(collection='documents', vectors=embeddings, metadata={...})│   │
│  │                                                                              │   │
│  │  Step 7: Extract Knowledge Graph                                            │   │
│  │    entities = extract_entities(parsed_text)  # Parties, dates, amounts      │   │
│  │    relationships = extract_relationships(parsed_text)                       │   │
│  │    neo4j.create_nodes(entities)                                             │   │
│  │    neo4j.create_relationships(relationships)                                │   │
│  │                                                                              │   │
│  │  Step 8: Update Job Status                                                  │   │
│  │    postgres.update(job_id, status='COMPLETED')                              │   │
│  │    postgres.update(document_id, status='READY')                             │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         QUERY SERVICE (FastAPI)                              │   │
│  │                                                                              │   │
│  │  POST /query/ask                                                             │   │
│  │    1. Query Translation (rephrase for better retrieval)                     │   │
│  │    2. Query Routing (vector search vs graph traversal)                      │   │
│  │    3. Retrieval (Qdrant similarity search)                                  │   │
│  │    4. Re-ranking (Cohere rerank)                                            │   │
│  │    5. LangGraph Orchestration (Self-RAG workflow)                           │   │
│  │    6. Generation (GPT-4o-mini with citations)                               │   │
│  │    7. GuardRails (check for hallucinations)                                 │   │
│  │    8. Return response with sources                                          │   │
│  │                                                                              │   │
│  │  GET /query/stream                                                           │   │
│  │    Same as above but streams tokens via SSE                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      EXTRACTION SERVICE                                      │   │
│  │                                                                              │   │
│  │  POST /extract/clauses                                                       │   │
│  │    Extract specific clauses (termination, liability, SLA)                   │   │
│  │                                                                              │   │
│  │  POST /extract/report                                                        │   │
│  │    Generate summary report of vendor agreement                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                    │                                 │
                    ▼                                 ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│        QDRANT                │  │         NEO4J                │
│     (Port 6333)              │  │      (Port 7687)             │
│                              │  │                              │
│  Collection: documents       │  │  Nodes:                      │
│                              │  │  - Document                  │
│  Vector: [0.123, -0.456, ...]│  │  - Party (Vendor, Client)    │
│  Metadata:                   │  │  - Clause                    │
│    - document_id             │  │  - Date                      │
│    - chunk_index             │  │  - Amount                    │
│    - text                    │  │                              │
│    - page_number             │  │  Relationships:              │
│                              │  │  - HAS_CLAUSE                │
│  Fast similarity search      │  │  - INVOLVES_PARTY            │
│  for semantic retrieval      │  │  - EFFECTIVE_DATE            │
│                              │  │                              │
│                              │  │  Graph traversal for         │
│                              │  │  cross-document analysis     │
└──────────────────────────────┘  └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           OBSERVABILITY LAYER                                       │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         LANGFUSE (Port 3001)                                 │   │
│  │                                                                              │   │
│  │  Traces:                                                                     │   │
│  │  - Ingestion pipeline (parse → chunk → embed → store)                       │   │
│  │  - Query pipeline (translate → retrieve → rerank → generate)                │   │
│  │                                                                              │   │
│  │  Metrics:                                                                    │   │
│  │  - Token usage per request                                                  │   │
│  │  - Cost per document processed                                              │   │
│  │  - Latency (p50, p95, p99)                                                  │   │
│  │  - Error rates                                                               │   │
│  │                                                                              │   │
│  │  Feedback:                                                                   │   │
│  │  - User ratings on responses                                                │   │
│  │  - Citation accuracy                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Document Upload (CQRS Write Path)

```
User Uploads PDF (50MB)
        │
        ▼
Next.js Client
  - FormData with file
  - sessionId
        │
        ▼
Node.js Gateway
  ├─ Validate JWT ✓
  ├─ Validate file type ✓
  ├─ Stream to MinIO ✓
  │    └─ s3://documents/user1/sess1/uuid.pdf
  ├─ Write to PostgreSQL ✓
  │    ├─ Document (status: PENDING)
  │    └─ Job (status: QUEUED)
  ├─ Push to Redis Queue ✓
  │    └─ bull:document-ingestion
  │         { jobId, documentId, userId, pdfUrl }
  └─ Return 202 Accepted ✓
       { jobId: "job_123", status: "QUEUED" }
        │
        ▼
Client Polls Job Status
  - GET /api/v1/jobs/job_123
  - Every 2 seconds
        │
        ▼
Python Worker (Background)
  ├─ Pop from Redis Queue
  ├─ Update Job: IN_PROGRESS
  ├─ Download PDF from MinIO
  ├─ Parse with LlamaParse (2-5 min)
  ├─ Chunk text (500 tokens)
  ├─ Generate embeddings (OpenAI)
  ├─ Store in Qdrant
  ├─ Extract entities → Neo4j
  ├─ Update Job: COMPLETED
  └─ Update Document: READY
        │
        ▼
Client Receives Status Update
  - Job status: COMPLETED
  - Document ready for querying
```

## Data Flow: Query (CQRS Read Path)

```
User Asks: "What's the termination clause?"
        │
        ▼
Next.js Client
  - POST /api/v1/ai/query
  - { sessionId, message }
        │
        ▼
Node.js Gateway
  ├─ Validate JWT ✓
  ├─ Check rate limit ✓
  ├─ Proxy to Python AI Service
  └─ Stream response back
        │
        ▼
Python Query Service
  ├─ Query Translation
  │    "termination clause" → "contract termination conditions notice period"
  ├─ Query Routing
  │    → Vector search (semantic)
  ├─ Qdrant Retrieval
  │    → Top 10 chunks (similarity > 0.7)
  ├─ Cohere Re-ranking
  │    → Top 5 chunks (relevance)
  ├─ LangGraph Orchestration
  │    ├─ Check if answer is in context
  │    ├─ Generate answer with GPT-4o-mini
  │    └─ Verify no hallucinations
  ├─ Extract Citations
  │    → [Document: MSA.pdf, Page: 12]
  └─ Return Response
        │
        ▼
Client Displays Answer
  - Streaming text
  - Citations as links
  - Save to Message table
```

## Fault Tolerance

```
Scenario: Python Worker Crashes on Page 199/200

┌─────────────────────────────────────────────────────────────┐
│ Python Worker                                               │
│   Processing page 199... CRASH! 💥                          │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ BullMQ (Redis)                                              │
│   Job not acknowledged → Re-queue after timeout             │
│   Retry attempt 1/3                                         │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Python Worker 2 (Different Pod)                             │
│   Picks up job → Processes successfully ✓                   │
└─────────────────────────────────────────────────────────────┘

Meanwhile:
┌─────────────────────────────────────────────────────────────┐
│ Node.js Gateway                                             │
│   Still serving requests ✓                                  │
│   No impact on other users ✓                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Next.js Client                                              │
│   User can navigate away ✓                                  │
│   Upload more documents ✓                                   │
│   Chat with other documents ✓                               │
└─────────────────────────────────────────────────────────────┘
```

## Scalability

```
Load: 1000 concurrent uploads

┌─────────────────────────────────────────────────────────────┐
│ Kubernetes Cluster                                          │
│                                                             │
│  Node.js Gateway Pods: 5 replicas                           │
│    ├─ Pod 1: Handling 200 requests                          │
│    ├─ Pod 2: Handling 200 requests                          │
│    ├─ Pod 3: Handling 200 requests                          │
│    ├─ Pod 4: Handling 200 requests                          │
│    └─ Pod 5: Handling 200 requests                          │
│                                                             │
│  Python Worker Pods: 10 replicas                            │
│    ├─ Worker 1-5: Processing documents                      │
│    └─ Worker 6-10: Idle, ready for jobs                     │
│                                                             │
│  Redis: Single instance (queue)                             │
│  PostgreSQL: Primary + Read Replicas                        │
│  MinIO: Distributed mode (4 nodes)                          │
│  Qdrant: Cluster mode (3 nodes)                             │
│  Neo4j: Cluster mode (3 nodes)                              │
└─────────────────────────────────────────────────────────────┘

Auto-scaling rules:
- Gateway: Scale up if CPU > 70%
- Workers: Scale up if queue length > 50
```

This is your production-ready, interview-winning architecture. 🚀
