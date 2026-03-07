# PolyGot Quick Commands

## 🚀 Start Everything

```bash
# 1. Start infrastructure (run once)
docker-compose up -d

# 2. Start Gateway (Terminal 1)
cd Gateway && npm run dev

# 3. Start Client (Terminal 2)
cd client && npm run dev

# 4. Start AI Worker (Terminal 3 - when implemented)
cd ai-service && python src/workers/ingestion_worker.py
```

## 🛑 Stop Everything

```bash
# Stop Docker services
docker-compose down

# Stop Node/Python with Ctrl+C in each terminal
```

## 🔍 Health Checks

```bash
# Gateway health
curl http://localhost:4000/health

# Check Docker services
docker ps

# Check Redis
docker exec -it gateway_redis redis-cli -a gateway_redis_pass_2024 ping

# Check PostgreSQL
docker exec -it gateway_postgres psql -U gateway_user -d gateway_db -c "SELECT 1;"
```

## 📦 Database Commands

```bash
cd Gateway

# Generate Prisma Client
npx prisma generate

# Run migrations
npx prisma migrate dev

# Reset database (WARNING: deletes data)
npx prisma migrate reset

# Open Prisma Studio (GUI)
npx prisma studio
```

## 🐳 Docker Commands

```bash
# View logs
docker-compose logs -f

# View specific service logs
docker logs gateway_postgres
docker logs gateway_redis
docker logs gateway_minio

# Restart a service
docker-compose restart postgres

# Remove all containers and volumes (NUCLEAR OPTION)
docker-compose down -v
```

## 📊 MinIO Commands

```bash
# Access MinIO Console
# Browser: http://localhost:9001
# Login: minioadmin / minioadmin

# List buckets (from inside container)
docker exec -it gateway_minio mc ls /data
```

## 🧪 Test API Endpoints

```bash
# Register user
curl -X POST http://localhost:4000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!","name":"Test User"}'

# Login
curl -X POST http://localhost:4000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!"}'

# Create session (replace TOKEN)
curl -X POST http://localhost:4000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -H "Cookie: token=YOUR_JWT_TOKEN" \
  -d '{"title":"Test Session"}'

# Upload document (replace TOKEN and SESSION_ID)
curl -X POST http://localhost:4000/api/v1/documents/upload \
  -H "Cookie: token=YOUR_JWT_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "sessionId=SESSION_ID"
```

## 🔧 Troubleshooting

```bash
# Clear Redis cache
docker exec -it gateway_redis redis-cli -a gateway_redis_pass_2024 FLUSHALL

# Check PostgreSQL tables
docker exec -it gateway_postgres psql -U gateway_user -d gateway_db -c "\dt"

# View PostgreSQL data
docker exec -it gateway_postgres psql -U gateway_user -d gateway_db -c "SELECT * FROM \"User\";"

# Rebuild Gateway
cd Gateway && npm run build

# Reinstall dependencies
cd Gateway && rm -rf node_modules package-lock.json && npm install
```

## 📝 Git Workflow

```bash
# Check status
git status

# Stage changes
git add .

# Commit
git commit -m "feat: implement CQRS upload flow"

# Push
git push origin main
```

## 🎯 URLs Reference

| Service | URL | Credentials |
|---------|-----|-------------|
| Client | http://localhost:3000 | - |
| Gateway | http://localhost:4000 | - |
| Gateway Health | http://localhost:4000/health | - |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Prisma Studio | http://localhost:5555 | - |
| PostgreSQL | localhost:5432 | gateway_user / gateway_secure_pass_2024 |
| Redis | localhost:6379 | gateway_redis_pass_2024 |

## 🐍 Python Setup (AI Service)

```bash
cd ai-service

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run worker
python src/workers/ingestion_worker.py
```

## 📦 Package Management

```bash
# Gateway - Add package
cd Gateway && npm install package-name

# Client - Add package
cd client && npm install package-name

# AI Service - Add package
cd ai-service && pip install package-name
```

## 🔐 Environment Variables

```bash
# Gateway
Gateway/.env

# Client
client/.env.local

# AI Service
ai-service/.env
```

## 🎨 Code Quality

```bash
# Lint Gateway
cd Gateway && npm run lint

# Lint Client
cd client && npm run lint

# Format Python
cd ai-service && black src/
```
