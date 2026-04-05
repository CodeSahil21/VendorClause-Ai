# VendorClause-ai

PolyGot is an end-to-end AI document intelligence platform for legal-style workflows.

It provides:

- Secure auth and session management
- PDF upload and asynchronous ingestion
- Hybrid retrieval (vector + graph)
- Streaming, source-grounded chat answers

The repository is organized as a multi-service workspace:

- `client/`: Next.js frontend
- `Gateway/`: Node.js/Express API, auth, sessions, upload, queue producer, Socket.IO bridge
- `ai-service/`: Python workers for ingestion and retrieval, plus MCP servers
- `docker-compose.yml`: local infra (Postgres, Redis, MinIO, Qdrant, Neo4j, MongoDB, Ollama, Langfuse)

## High-Level Architecture

```mermaid
flowchart LR
	UI[Client Next.js App] -->|REST + Cookies| GW[Gateway API + Socket.IO]

	GW --> PG[(PostgreSQL)]
	GW --> RE[(Redis)]
	GW --> MQ[(BullMQ)]
	GW --> MI[(MinIO)]

	MQ --> IW[Ingestion Worker]
	IW --> QD[(Qdrant)]
	IW --> N4[(Neo4j)]
	IW --> PG
	IW --> RE

	GW -->|query:request| RE
	RE --> QW[Query Worker]
	QW --> QMCP[Qdrant MCP Server]
	QW --> NMCP[Neo4j MCP Server]
	QMCP --> QD
	NMCP --> N4
	QW --> PG
	QW -->|stream events| RE
	RE --> GW
	GW -->|token stream| UI
```

## System Design Diagram 1: Ingestion Workflow

```mermaid
flowchart TB
	classDef step fill:#ffffff,stroke:#374151,stroke-width:1.5,color:#111827
	classDef io fill:#f8fbff,stroke:#1d4ed8,stroke-width:1.5,color:#1e3a8a
	classDef store fill:#fffef8,stroke:#92400e,stroke-width:1.5,color:#7c2d12

	A[Client uploads PDF]:::step --> B[Gateway stores object in MinIO\nand creates Document + Job QUEUED]:::step
	B --> C[Gateway adds BullMQ job\nqueue=document-ingestion\nname=process-document]:::step
	C --> D[IngestionWorker process_job]:::step

	D --> E[Validate payload: jobId/documentId/pdfUrl]:::step
	E --> F[Set Job IN_PROGRESS\nSet Document PROCESSING]:::step
	F --> G[Download PDF from MinIO URL\nminio://bucket/key to temp file]:::step

	G --> H[Pipeline stage: parse_pdf\nLlamaParse markdown extraction]:::step
	H --> I[Pipeline stage: chunk\nDocumentChunker with metadata]:::step
	I --> J[Pipeline stage: parallel_extract_and_index]:::step

	J --> K[VectorIndexer indexes all chunks\nHuggingFace dense + Splade sparse -> Qdrant]:::step
	J --> L[GraphExtractor on high-value chunks\nimportance >= 2 fallback all]:::step

	L --> M[Neo4jService create_document_node + store_graph_documents]:::step
	K --> N[Finalize job/document status]:::step
	M --> N

	N --> O[Set Job COMPLETED\nSet Document READY]:::step
	O --> P[Publish job progress/status events]:::step

	Q[(PostgreSQL)]:::store
	R[(MinIO)]:::store
	S[(Qdrant)]:::store
	T[(Neo4j)]:::store
	U[(Redis)]:::io

	F --> Q
	G --> R
	K --> S
	M --> T
	P --> U
```

## System Design Diagram 2: Retrieval Workflow

```mermaid
flowchart TB
	classDef node fill:#ffffff,stroke:#374151,stroke-width:1.5,color:#111827
	classDef dec fill:#f8fbff,stroke:#1d4ed8,stroke-width:1.5,color:#1e3a8a

	A([Start]) --> B[supervisor]:::node
	B --> C[rewriter]:::node

	C --> D{route_after_rewriter}:::dec
	D -->|complex query| E[decomposer]:::node
	D -->|simple query| F[mcp_orchestrator]:::node
	E --> F

	F --> G[bridge_fusion]:::node
	G --> H[crag_evaluator]:::node

	H --> I{route_after_crag}:::dec
	I -->|sufficient| J[generator]:::node
	I -->|insufficient and crag_iteration < 2| C
	I -->|partial or crag_iteration >= 2| J

	J --> K([End])
```

## Tech Stack

- Frontend: Next.js 16, React 19, TypeScript, Zustand, Socket.IO client
- Gateway: Node.js, Express, Prisma, BullMQ, Redis, MinIO, Socket.IO
- AI Service: Python, LangGraph, LangChain, LlamaParse, Qdrant, Neo4j
- Infrastructure: Docker Compose

## Monorepo Structure

```text
PolyGot/
  client/          # Frontend app
  Gateway/         # API gateway service
  ai-service/      # Ingestion + retrieval workers + MCP servers
  diagrams/        # Mermaid diagrams
  docker-compose.yml
```

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Node.js 20+
- npm
- Python 3.11+ (recommended)

## Quick Start (Local Development)

### 1) Start infrastructure

From repository root:

```powershell
docker-compose up -d
```

This starts:

- PostgreSQL (`5432`)
- Redis (`6379`)
- MinIO (`9000`, console `9001`)
- Qdrant (`6333`)
- Neo4j (`7474`, bolt `7687`)
- MongoDB (`27017`)
- Ollama (`11434`)
- Langfuse (`3300`)

### 2) Configure and run Gateway

```powershell
cd Gateway
npm install
```

Create `Gateway/.env` with at least:

```env
NODE_ENV=development
PORT=4000
FRONTEND_URL=http://localhost:3400

DATABASE_URL=postgresql://gateway_user:gateway_secure_pass_2024@localhost:5432/gateway_db

JWT_SECRET=replace_with_a_32_plus_character_secret
JWT_EXPIRES_IN=7d

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=example_user
SMTP_PASS=example_password

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=gateway_redis_pass_2024

MINIO_ENDPOINT=localhost
MINIO_PORT=9000
MINIO_USE_SSL=false
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=documents

QDRANT_MCP_URL=http://localhost:8001
NEO4J_MCP_URL=http://localhost:8002
MCP_AUTH_KEY=optional_shared_key
```

Run migrations and start:

```powershell
npx prisma migrate deploy
npm run dev
```

Gateway will run at `http://localhost:4000`.

### 3) Configure and run AI service

```powershell
cd ai-service
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Update `ai-service/.env` values, especially:

- `LLAMA_CLOUD_API_KEY`
- `OPENAI_API_KEY`
- `MCP_AUTH_KEY` (if used)

Start 4 processes in separate terminals:

```powershell
python -m src.mcp_servers.qdrant_mcp_server
```

```powershell
python -m src.mcp_servers.neo4j_mcp_server
```

```powershell
python -m src.ingestion.worker
```

```powershell
python -m src.retrieval.query_worker
```

### 4) Configure and run client

```powershell
cd client
npm install
```

Create `client/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:4000/api/v1
```

Start frontend:

```powershell
npm run dev
```

Client will run at `http://localhost:3400`.

## Runtime Flow Summary

1. User uploads PDF from client.
2. Gateway stores the file in MinIO and enqueues ingestion via BullMQ.
3. Ingestion worker parses, chunks, embeds, and writes data to Qdrant/Neo4j.
4. User asks a question in the session chat.
5. Gateway publishes query request to Redis.
6. Query worker runs retrieval graph and publishes streaming events.
7. Gateway forwards streaming response to client via Socket.IO.

## Key Ports

- Client: `3400`
- Gateway: `4000`
- Qdrant MCP: `8001`
- Neo4j MCP: `8002`
- PostgreSQL: `5432`
- Redis: `6379`
- MinIO API: `9000`
- MinIO Console: `9001`
- Qdrant: `6333`
- Neo4j Browser: `7474`
- Neo4j Bolt: `7687`
- MongoDB: `27017`
- Ollama: `11434`
- Langfuse: `3300`

## Useful Commands

From project root:

```powershell
docker-compose up -d
docker-compose ps
docker-compose logs -f
docker-compose down
```

Gateway:

```powershell
cd Gateway
npm run dev
```

Client:

```powershell
cd client
npm run dev
```

AI service:

```powershell
cd ai-service
.\venv\Scripts\Activate.ps1
python -m src.ingestion.worker
python -m src.retrieval.query_worker
```

## Troubleshooting

- If login/upload fails, check `NEXT_PUBLIC_API_URL` and `FRONTEND_URL` alignment (`3400` vs `4000`).
- If ingestion does not start, verify Gateway is connected to Redis and BullMQ queue is initialized.
- If status updates do not appear, verify Redis pub/sub and Gateway Socket.IO bridge are running.
- If retrieval fails, verify both MCP servers are running on `8001` and `8002`.
- If vector/graph look empty, verify Qdrant and Neo4j containers are healthy.

## License

This project currently has no explicit open-source license file.
