# PolyGot

PolyGot is an end-to-end legal document intelligence platform.

It supports:

- Secure auth and session management
- PDF upload and ingestion pipeline
- Hybrid retrieval (vector + graph)
- Streaming, citation-aware AI answers
- Real-time progress and query updates

This README is the single project-level guide for understanding architecture, data flow, and local setup.

## 1. Monorepo Layout

- `client`: Next.js frontend app
- `Gateway`: Express + Prisma API and Socket.IO bridge
- `ai-service`: Python ingestion/retrieval workers and MCP servers
- `docker-compose.yml`: local infrastructure stack

## 2. System Design (Deep View)

This section gives in-depth diagrams for architecture and communication.

### 2.1 Container-Level Architecture

```mermaid
flowchart TB
    classDef node fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
    classDef runtime fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
    classDef store fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
    classDef obs fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827

    subgraph L1[Level 1 - User]
      USER[User Browser]
    end

    subgraph L2[Level 2 - Interface]
      CLIENT[Client App<br/>Next.js + React<br/>Port 3400]
    end

    subgraph L3[Level 3 - Gateway]
      GATEWAY[Gateway API<br/>Express + Prisma + Socket.IO<br/>Port 4000]
    end

    subgraph L4[Level 4 - Async Runtime]
      REDIS[(Redis<br/>Queue + PubSub)]
      INGEST[Ingestion Worker<br/>src.ingestion.worker]
      QUERY[Query Worker<br/>src.retrieval.query_worker]
      QMCP[Qdrant MCP<br/>Port 8001]
      NMCP[Neo4j MCP<br/>Port 8002]
    end

    subgraph L5[Level 5 - Data Plane]
      POSTGRES[(PostgreSQL<br/>users sessions docs jobs messages)]
      MINIO[(MinIO<br/>pdf objects)]
      QDRANT[(Qdrant<br/>vector index)]
      NEO4J[(Neo4j<br/>knowledge graph)]
      MONGO[(MongoDB optional<br/>checkpointing)]
    end

    subgraph L6[Level 6 - Observability]
      LANGFUSE[(Langfuse<br/>traces)]
    end

    USER --> CLIENT
    CLIENT -->|REST + Socket.IO| GATEWAY

    GATEWAY -->|state| POSTGRES
    GATEWAY -->|file objects| MINIO
    GATEWAY -->|enqueue + publish| REDIS
    GATEWAY -->|stream forwarding| CLIENT

    REDIS -->|document-ingestion jobs| INGEST
    REDIS -->|query:request:*| QUERY

    INGEST -->|metadata + status| POSTGRES
    INGEST -->|read source| MINIO
    INGEST -->|vector + graph writes| QMCP
    INGEST -->|graph writes| NMCP

    QUERY -->|message persistence| POSTGRES
    QUERY -->|stream + checkpoints| REDIS
    QUERY -->|checkpoints| MONGO
    QUERY -->|retrieval calls| QMCP
    QUERY -->|retrieval calls| NMCP

    QMCP -->|Qdrant ops| QDRANT
    NMCP -->|Neo4j ops| NEO4J

    INGEST --> LANGFUSE
    QUERY --> LANGFUSE

    class USER,CLIENT,GATEWAY node
    class INGEST,QUERY,QMCP,NMCP runtime
    class POSTGRES,REDIS,MINIO,QDRANT,NEO4J,MONGO store
    class LANGFUSE obs
```

### 2.2 Ingestion Pipeline (Internal Components)

```mermaid
flowchart TB
  classDef stage fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef decision fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef store fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827

    JOB[Load job payload]
    START[Set IN_PROGRESS]
    FETCH[Fetch PDF]
    PARSE[Parse PDF]
    CHUNK[Chunk + metadata]
    GRAPH[Extract graph]
    VECTOR[Create embeddings]
  D1{Extraction Valid?}
    UPV[Upsert vectors]
    UPG[Upsert graph]
    FINAL[Finalize COMPLETED]
    FAIL[Finalize FAILED]

  PG[(PostgreSQL)]
  MN[(MinIO)]
  QD[(Qdrant)]
  N4[(Neo4j)]
    RD[(Redis)]

    subgraph PIPE[Worker pipeline]
      JOB --> START --> FETCH --> PARSE --> CHUNK --> GRAPH --> VECTOR --> D1
      D1 -->|yes| UPV
      D1 -->|yes| UPG
      D1 -->|no| FAIL
      UPV --> FINAL
      UPG --> FINAL
    end

    FETCH -->|read| MN
  UPV --> QD
  UPG --> N4

    START -->|set processing| PG
    FINAL -->|set ready| PG
    FAIL -->|set failed| PG

    START -->|job status| RD
    FINAL -->|job completed| RD
    FAIL -->|job failed| RD

  class JOB,START,FETCH,PARSE,CHUNK,GRAPH,VECTOR,UPV,UPG,FINAL,FAIL stage
  class D1 decision
  class PG,MN,QD,N4,RD store
```

### 2.3 Retrieval + Generation Pipeline (LangGraph)

```mermaid
flowchart TB
    classDef node fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
    classDef decision fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
    classDef io fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827

  START([Query Request]) --> LOAD[Load Session Context\nchat history + metadata]
  LOAD --> SUP[Supervisor\nintent strategy entities]
  SUP --> RW[Rewriter\nnormalize legal phrasing]

  RW --> D1{Need decomposition?}
  D1 -->|yes| DEC[Decomposer\nsub-query list]
  D1 -->|no| ORCH[MCP Orchestrator\nparallel retrieval]
  DEC --> ORCH

  ORCH --> QCALL[Qdrant MCP calls\nvector_search filter]
  ORCH --> NCALL[Neo4j MCP calls\ngraph_traverse extract_entity]
  QCALL --> QRES[(Vector Candidates)]
  NCALL --> NRES[(Graph Candidates)]

  QRES --> BF[Bridge Fusion\nRRF + rerank + dedupe]
  NRES --> BF
  BF --> CRAG[CRAG Evaluator\nquality and sufficiency]
  CRAG --> D2{Context sufficient?}
  D2 -->|no and retry budget exists| RW
  D2 -->|yes or retry budget exhausted| GEN[Generator\ncompose grounded answer]

  GEN --> HCHK[Faithfulness Check\nhallucination gate]
  HCHK --> D3{Passes quality gate?}
  D3 -->|yes| TOK[stream:token]
  D3 -->|yes| SRC[stream:sources]
  D3 -->|yes| FIN[stream:done]
  D3 -->|no| ERR[stream:error]

  class START,LOAD,SUP,RW,DEC,ORCH,BF,CRAG,GEN,HCHK node
  class D1,D2,D3 decision
  class TOK,SRC,FIN,ERR,QCALL,NCALL,QRES,NRES io
```

### 2.4 Communication Contracts and Channels

```mermaid
flowchart LR
  classDef req fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef evt fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef q fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827

    subgraph REQ[Request path]
      C[Client] -->|POST /api/v1/documents/upload| G[Gateway]
      C -->|POST /api/v1/sessions/:sessionId/query| G
    end

    subgraph BUS[Redis channels]
      R[(Redis)]
    end

    subgraph WORKERS[Consumers]
      IW[Ingestion Worker]
      QW[Query Worker]
    end

    G -->|enqueue document-ingestion| R
    R -->|consume queue| IW
    IW -->|job:progress + job:status| R

    G -->|publish query:request:sessionId| R
    R -->|consume query:request:*| QW
    QW -->|query:stream:sessionId\nstream:token| R
    QW -->|query:stream:sessionId\nstream:sources| R
    QW -->|query:stream:sessionId\nstream:done| R
    QW -->|query:stream:sessionId\nstream:error| R

    R -->|Gateway subscribes and bridges| G
    G -->|Socket.IO room forwarding| C

  class C,G,IW,QW req
  class R q
```

## 3. Ingestion Workflow (Execution Timeline)

Ingestion starts when a user uploads a PDF in the client.

```mermaid
flowchart TB
  classDef phase fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef action fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef store fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef decision fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827

  subgraph P1[Phase 1 - Upload and Queue]
    direction TB
    C1[Client uploads PDF] --> G1[Gateway stores PDF in MinIO]
    G1 --> G2[Gateway creates document and queued job in PostgreSQL]
    G2 --> G3[Gateway enqueues ingestion job in Redis BullMQ]
    G3 --> C2[Gateway returns 202 to client]
  end

  subgraph P2[Phase 2 - Worker Processing]
    direction TB
    W1[Ingestion worker consumes job] --> W2[Set processing state]
    W2 --> W3[Download PDF]
    W3 --> W4[Parse and chunk]
    W4 --> W5[Extract entities and relations]
  end

  subgraph P3[Phase 3 - Parallel Indexing]
    direction LR
    W5 --> V1[Upsert vectors in Qdrant]
    W5 --> N1[Upsert graph in Neo4j]
  end

  subgraph P4[Phase 4 - Finalize and Notify]
    direction TB
    D1{Ingestion result}
    D1 -->|success| S1[Set completed and ready in PostgreSQL]
    D1 -->|failure| F1[Set failed in PostgreSQL]
    S1 --> S2[Publish job completed in Redis]
    F1 --> F2[Publish job failed in Redis]
    S2 --> C3[Gateway forwards status via socket room]
    F2 --> C3
  end

  W1 --> D1

  class C1,C2,C3,G1,G2,G3,W1,W2,W3,W4,W5,V1,N1,S1,S2,F1,F2 action
  class D1 decision
```

## 4. Query Retrieval and Streaming Workflow (Execution Timeline)

Retrieval starts when the user asks a question in a READY session.

```mermaid
flowchart TB
  classDef phase fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef action fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef io fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827
  classDef decision fill:#ffffff,stroke:#374151,stroke-width:2,color:#111827

  subgraph Q1[Phase 1 - Request and Dispatch]
    direction TB
    A1[Client submits question] --> A2[Gateway validates auth ownership rate limit]
    A2 --> A3[Gateway publishes query request to Redis]
    A3 --> A4[Query worker consumes request]
    A4 --> A5[Persist user message in PostgreSQL]
  end

  subgraph Q2[Phase 2 - Retrieval]
    direction TB
    B1[Run LangGraph retrieval] --> B2[Supervisor and rewrite]
    B2 --> B3[Qdrant MCP vector retrieval]
    B2 --> B4[Neo4j MCP graph retrieval]
    B3 --> B5[Fusion and rerank]
    B4 --> B5
    B5 --> D2{CRAG sufficient?}
    D2 -->|no retry| B2
    D2 -->|yes| B6[Generate grounded answer]
  end

  subgraph Q3[Phase 3 - Stream and Finalize]
    direction TB
    B6 --> C1[Publish stream token events]
    C1 --> C2[Publish stream sources]
    C2 --> C3[Persist AI message in PostgreSQL]
    C3 --> D3{Generation result}
    D3 -->|success| C4[Publish stream done]
    D3 -->|failure| C5[Publish stream error]
    C4 --> C6[Gateway forwards stream to session room]
    C5 --> C6
  end

  A5 --> B1

  class A1,A2,A3,A4,A5,B1,B2,B3,B4,B5,B6,C1,C2,C3,C4,C5,C6 action
  class D2,D3 decision
```

## 5. LangGraph Retrieval Design

The query worker uses a LangGraph state machine in `ai-service/src/retrieval/graph.py`.

Core nodes:

- Supervisor: classify intent, strategy, entities
- Rewriter: normalize query for recall and grounding
- Decomposer: split complex legal asks into atomic sub-queries
- MCP Orchestrator: parallel Qdrant and Neo4j retrieval calls
- Bridge Fusion: combine graph-linked chunks + vector hits with RRF
- CRAG Evaluator: decide sufficient/partial/insufficient context
- Generator: stream answer, attach sources, run hallucination checker

High-level route logic:

- `supervisor -> rewriter`
- `rewriter -> decomposer` for multi-part questions, otherwise direct retrieval
- `... -> mcp_orchestrator -> bridge_fusion -> crag_evaluator`
- CRAG can retry rewrite on insufficient evidence
- Final response generated only after context gate

## 6. Tech Stack by Layer

Client:

- Next.js 16, React 19, TypeScript
- Zustand state management
- Axios + cookie auth
- Socket.IO client for live events

Gateway:

- Express 5, TypeScript
- Prisma + PostgreSQL
- Redis + BullMQ queue producer
- MinIO document storage
- Socket.IO Redis-stream bridge
- TypeBox + AJV validation

AI service:

- FastAPI MCP servers
- BullMQ Python worker consumers
- LangGraph orchestration
- LangChain + OpenAI models
- LlamaParse for PDF parsing
- Qdrant dense+sparse hybrid retrieval
- Neo4j graph extraction/traversal
- Langfuse observability
- MongoDB optional checkpoint backend

Infrastructure:

- PostgreSQL
- Redis
- MinIO
- Qdrant
- Neo4j
- MongoDB
- Langfuse
- Ollama (optional)

## 7. Performance and Reliability Boosts

Implemented optimization patterns include:

- Parallel retrieval calls (Qdrant + Neo4j) through MCP orchestrator
- Reciprocal Rank Fusion plus rerank for quality boost
- Singleton/shared clients for Redis, DB, and MCP HTTP transport
- Worker heartbeat checks before query dispatch
- Retry and timeout logic around external model/tool calls
- Cache-assisted session/document reads in Gateway
- Graceful shutdown and cancellation handling in workers
- Best-effort stale-data cleanup in Qdrant and Neo4j on document delete

## 8. API and Event Contracts

Gateway API docs:

- `Gateway/Api docs.md`

Client docs:

- `client/README.md`

AI service docs:

- `ai-service/README.md`

Key query stream events:

- `stream:token`
- `stream:sources`
- `stream:done`
- `stream:error`

Key job events:

- `job:progress`
- `job:status`

## 9. Local Setup (Full Stack)

### 9.1 Start infrastructure

From repository root:

```powershell
docker compose up -d
```

### 9.2 Start Gateway

```powershell
cd Gateway
npm install
npm run dev
```

### 9.3 Start Client

```powershell
cd client
npm install
npm run dev
```

### 9.4 Start AI Service processes

In separate terminals:

```powershell
cd ai-service
python -m src.mcp_servers.qdrant_mcp_server
```

```powershell
cd ai-service
python -m src.mcp_servers.neo4j_mcp_server
```

```powershell
cd ai-service
python -m src.ingestion.worker
```

```powershell
cd ai-service
python -m src.retrieval.query_worker
```

## 10. Typical User Journey

1. User logs in.
2. User creates a session.
3. User uploads one PDF to the session.
4. Client receives ingestion progress updates in real time.
5. Once status is READY, user asks a question.
6. Client receives streamed answer tokens and final cited response.

## 11. Security and Controls

- JWT auth with httpOnly cookie handling
- Protected API routes with ownership checks
- Query endpoint per-user rate limiting (20 queries/min)
- Upload endpoint type and size validation (PDF, max 50MB)
- MCP server API-key gate for tool calls

## 12. Contribution Notes

When making changes:

- Keep contracts backward compatible between client, gateway, and ai-service
- Update component-level docs in each service README
- Update `Gateway/Api docs.md` for any endpoint/event changes
- Include migration notes when changing DB schema or message/event shape

## 13. License and Internal Use

Add your project license policy here (MIT/Apache-2.0/Internal).
