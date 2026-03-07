# PolyGot Setup Guide

## Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- Docker Desktop (for Windows)
- Git

---

## Step 1: Infrastructure Setup (Docker Services)

### 1.1 Start Docker Services

```bash
# From project root
docker-compose up -d
```

This starts:
- **PostgreSQL** (port 5432)
- **Redis** (port 6379)
- **MinIO** (port 9000, console 9001)

### 1.2 Verify Services

```bash
# Check running containers
docker ps

# Should see 3 containers:
# - gateway_postgres
# - gateway_redis
# - gateway_minio
```

### 1.3 Access MinIO Console

1. Open http://localhost:9001
2. Login: `minioadmin` / `minioadmin`
3. Bucket `documents` will be auto-created by Gateway on first run

---

## Step 2: Gateway (Node.js) Setup

### 2.1 Install Dependencies

```bash
cd Gateway
npm install
```

### 2.2 Environment Variables

Your `.env` is already configured. Verify these key values:

```env
PORT=4000
DATABASE_URL=postgresql://gateway_user:gateway_secure_pass_2024@localhost:5432/gateway_db
JWT_SECRET=your-super-secret-jwt-key-min-32-chars
REDIS_PASSWORD=gateway_redis_pass_2024
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### 2.3 Database Migration

```bash
# Generate Prisma Client
npx prisma generate

# Run migrations
npx prisma migrate dev --name init

# (Optional) Seed database
npx prisma db seed
```

### 2.4 Start Gateway

```bash
npm run dev
```

Gateway runs on **http://localhost:4000**

### 2.5 Test Gateway

```bash
# Health check
curl http://localhost:4000/health

# Expected response:
# {"statusCode":200,"data":{"status":"OK","database":"connected",...}}
```

---

## Step 3: Client (Next.js) Setup

### 3.1 Install Dependencies

```bash
cd client
npm install
```

### 3.2 Environment Variables

Check `client/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:4000/api/v1
```

### 3.3 Start Client

```bash
npm run dev
```

Client runs on **http://localhost:3000**

---

## Step 4: AI Service (Python) Setup

### 4.1 Create Python Environment

```bash
cd ai-service
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 4.2 Install Dependencies

```bash
pip install fastapi uvicorn python-multipart boto3 redis bullmq-python
pip install llama-parse langchain qdrant-client neo4j
pip install openai langfuse
```

### 4.3 Create Basic Structure

```bash
mkdir -p src/services src/workers src/config
```

### 4.4 Environment Variables

Create `ai-service/.env`:

```env
# OpenAI
OPENAI_API_KEY=your-openai-key

# LlamaParse
LLAMA_CLOUD_API_KEY=your-llama-parse-key

# Redis (for BullMQ)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=gateway_redis_pass_2024

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents

# PostgreSQL
DATABASE_URL=postgresql://gateway_user:gateway_secure_pass_2024@localhost:5432/gateway_db

# Qdrant
QDRANT_URL=http://localhost:6333

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Langfuse
LANGFUSE_PUBLIC_KEY=your-key
LANGFUSE_SECRET_KEY=your-secret
LANGFUSE_HOST=http://localhost:3001
```

---

## Step 5: Add Missing Infrastructure (Optional)

### 5.1 Add Qdrant & Neo4j to Docker Compose

Update `docker-compose.yml`:

```yaml
  qdrant:
    image: qdrant/qdrant:latest
    container_name: gateway_qdrant
    restart: unless-stopped
    ports:
      - '6333:6333'
    volumes:
      - qdrant_data:/qdrant/storage

  neo4j:
    image: neo4j:5-community
    container_name: gateway_neo4j
    restart: unless-stopped
    ports:
      - '7474:7474'
      - '7687:7687'
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - neo4j_data:/data

volumes:
  postgres_data:
  redis_data:
  minio_data:
  qdrant_data:
  neo4j_data:
```

Then restart:

```bash
docker-compose down
docker-compose up -d
```

---

## Step 6: Implement CQRS Upload Flow

### 6.1 Install BullMQ in Gateway

```bash
cd Gateway
npm install bullmq
```

### 6.2 Create Queue Service

Create `Gateway/src/lib/queue.ts`:

```typescript
import { Queue } from 'bullmq';
import { env } from '../config';

export const ingestionQueue = new Queue('document-ingestion', {
  connection: {
    host: env.REDIS_HOST,
    port: env.REDIS_PORT,
    password: env.REDIS_PASSWORD
  }
});

export interface IngestionJobData {
  jobId: string;
  documentId: string;
  userId: string;
  pdfUrl: string;
}
```

### 6.3 Update Document Service

Modify `Gateway/src/services/document.service.ts`:

```typescript
import { ingestionQueue } from '../lib/queue';

// In uploadDocument method, after creating job:
await ingestionQueue.add('process-document', {
  jobId: job.id,
  documentId: document.id,
  userId,
  pdfUrl: s3Url
});

// Return 202 Accepted
return { document, job };
```

### 6.4 Update Document Controller

Modify `Gateway/src/controllers/document.controller.ts`:

```typescript
export const uploadDocument = asyncHandler(async (req: Request, res: Response) => {
  if (!req.file) {
    throw new ApiError(400, 'No file uploaded');
  }

  const result = await DocumentService.uploadDocument(
    req.user!.id, 
    req.body.sessionId, 
    req.file
  );
  
  // Return 202 Accepted with jobId
  res.status(202).json(new ApiResponse(202, result, 'Document queued for processing'));
});
```

### 6.5 Create Python Worker

Create `ai-service/src/workers/ingestion_worker.py`:

```python
import asyncio
from bullmq import Worker
from services.ingestion_service import process_document

async def process_job(job):
    data = job.data
    await process_document(
        job_id=data['jobId'],
        document_id=data['documentId'],
        user_id=data['userId'],
        pdf_url=data['pdfUrl']
    )

worker = Worker(
    'document-ingestion',
    process_job,
    {
        'connection': {
            'host': 'localhost',
            'port': 6379,
            'password': 'gateway_redis_pass_2024'
        }
    }
)

if __name__ == '__main__':
    print("🔄 Ingestion worker started")
    asyncio.run(worker.run())
```

---

## Step 7: Verification Checklist

### Infrastructure
- [ ] PostgreSQL running (port 5432)
- [ ] Redis running (port 6379)
- [ ] MinIO running (port 9000)
- [ ] Qdrant running (port 6333) - optional
- [ ] Neo4j running (port 7687) - optional

### Services
- [ ] Gateway health check passes
- [ ] Client loads at localhost:3000
- [ ] Can register/login user
- [ ] Can create chat session

### CQRS Flow
- [ ] Upload returns 202 with jobId
- [ ] Job status is QUEUED in database
- [ ] Python worker picks up job
- [ ] Job status updates to IN_PROGRESS
- [ ] Job completes with COMPLETED status

---

## Step 8: Development Workflow

### Start All Services

```bash
# Terminal 1: Infrastructure
docker-compose up

# Terminal 2: Gateway
cd Gateway && npm run dev

# Terminal 3: Client
cd client && npm run dev

# Terminal 4: AI Worker (when ready)
cd ai-service && python src/workers/ingestion_worker.py
```

### Stop All Services

```bash
# Stop Docker services
docker-compose down

# Stop Node/Python processes with Ctrl+C
```

---

## Troubleshooting

### PostgreSQL Connection Failed
```bash
# Check if container is running
docker ps | grep postgres

# Check logs
docker logs gateway_postgres

# Restart container
docker-compose restart postgres
```

### Redis Connection Failed
```bash
# Test Redis connection
docker exec -it gateway_redis redis-cli -a gateway_redis_pass_2024 ping
# Should return: PONG
```

### MinIO Bucket Not Created
```bash
# Manually create bucket
docker exec -it gateway_minio mc mb /data/documents
```

### Prisma Migration Issues
```bash
# Reset database (WARNING: deletes all data)
npx prisma migrate reset

# Force push schema
npx prisma db push --force-reset
```

---

## Next Steps

1. **Implement Python Ingestion Service** - LlamaParse + Chunking + Embeddings
2. **Add Query Service** - RAG pipeline with LangGraph
3. **Add Extraction Service** - Clause extraction
4. **Add Observability** - Langfuse integration
5. **Deploy to Production** - Kubernetes + Helm

---

## Architecture Summary

```
User Upload → Next.js (3000)
           ↓
Node.js Gateway (4000)
  ├─ Validate JWT
  ├─ Stream to MinIO
  ├─ Write to PostgreSQL (QUEUED)
  ├─ Push to Redis Queue
  └─ Return 202 Accepted
           ↓
Python Worker (background)
  ├─ Pop from Redis Queue
  ├─ Update PostgreSQL (IN_PROGRESS)
  ├─ Download from MinIO
  ├─ Process with LlamaParse
  ├─ Store in Qdrant + Neo4j
  └─ Update PostgreSQL (COMPLETED)
```

This is your **Logical Monolith, Physical Microservice** architecture in action.
