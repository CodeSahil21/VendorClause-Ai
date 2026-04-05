# PolyGot Client

Frontend application for the PolyGot legal document workflow.

This app lets users:

- Sign in and manage sessions
- Upload a PDF into a session
- Watch ingestion progress in real time
- Chat with the processed document using streamed responses

This README explains the client from basics so a new developer can understand, run, and extend it.

## 1) Quick Start

Prerequisites:

- Node.js 20+
- npm
- Running Gateway API server
- Running AI service workers and MCP servers

Steps:

1. Move into the client folder.
2. Install dependencies.
3. Create a local env file.
4. Start development server.

Commands:

	cd client
	npm install
	copy .env.example .env.local
	npm run dev

Default dev URL:

- http://localhost:3400

## 2) Environment Variables

Defined in [.env.example](.env.example):

- NEXT_PUBLIC_API_URL

What it means:

- Base API URL including version path, for example http://localhost:4000/api/v1

Important note:

- The current .env.example points to port 5000.
- Your local Gateway usually runs on 4000 in this project.
- If login or API calls fail, verify NEXT_PUBLIC_API_URL first.

## 3) Scripts

From [package.json](package.json):

- npm run dev: starts Next.js dev server on port 3400
- npm run build: production build
- npm run start: starts production server on port 3400
- npm run lint: runs ESLint

## 4) Core Tech Stack

- Next.js App Router
- React 19
- TypeScript
- Tailwind CSS
- Zustand for state
- Axios for HTTP API calls
- Socket.IO client for live updates
- React Markdown for rendering assistant responses
- React Hot Toast for notifications

## 5) High-Level Architecture

Client architecture diagram:

	Browser UI
	   |
	   v
	Next.js App Routes (app)
	   |
	   +--> Components (components)
	   |      - UploadDocument
	   |      - ProcessingDocument
	   |      - ChatDocument
	   |
	   +--> Zustand Stores (store)
	   |      - authStore
	   |      - sessionStore
	   |      - documentStore
	   |
	   +--> API Layer (api)
	   |      - auth.api
	   |      - session.api
	   |      - document.api
	   |      - axios instance + interceptors
	   |
	   +--> Socket Layer (context/SocketContext)
			  - job rooms
			  - session rooms

Backend interaction model:

	Client ----HTTP----> Gateway API
	Client ---Socket---> Gateway Socket.IO
	Gateway ---Redis---> AI Workers

## 6) Main Runtime Flows

### A) Document Upload and Ingestion Flow

	User uploads PDF
	   -> UploadDocument calls documentApi.uploadDocument
	   -> Gateway creates ingestion job and returns jobId
	   -> UI switches to ProcessingDocument
	   -> useJobStatus joins job room over Socket.IO
	   -> Receives job:status and job:progress
	   -> On completion, session reloads
	   -> Document status becomes READY
	   -> UI switches to ChatDocument

Key files:

- [components/UploadDocument.tsx](components/UploadDocument.tsx)
- [components/ProcessingDocument.tsx](components/ProcessingDocument.tsx)
- [hooks/useJobStatus.ts](hooks/useJobStatus.ts)
- [app/home/session/[sessionId]/page.tsx](app/home/session/[sessionId]/page.tsx)

### B) Query and Streaming Chat Flow

	User asks question
	   -> ChatDocument calls sessionApi.querySession
	   -> Gateway queues query to Redis
	   -> AI Query Worker processes
	   -> Gateway forwards stream events to session socket room
	   -> Client receives:
			stream:token   (incremental text)
			stream:sources (citations metadata)
			stream:done    (final answer)
			stream:error   (error handling)

Key files:

- [components/ChatDocument.tsx](components/ChatDocument.tsx)
- [api/session.api.ts](api/session.api.ts)
- [context/SocketContext.tsx](context/SocketContext.tsx)

## 7) Routing and Layout Structure

Primary route groups:

- app/(auth): login and registration pages
- app/home: authenticated area
- app/home/session/[sessionId]: session workspace (upload, processing, chat)

App shell and providers:

- [app/layout.tsx](app/layout.tsx): global shell, error boundary, store provider, auth initializer, toast provider
- [app/home/layout.tsx](app/home/layout.tsx): authenticated layout and Socket provider
- [components/AuthInitializer.tsx](components/AuthInitializer.tsx): auth hydration and route guard behavior

## 8) State Management

Zustand slices:

- authStore: login, logout, profile state
- sessionStore: session list and current session
- documentStore: upload and document status-related state

Store exports:

- [store/index.ts](store/index.ts)

Session state behavior:

- [store/slices/sessionStore.ts](store/slices/sessionStore.ts) keeps sessions, current session, loading, and error.

## 9) API Layer

Central API exports:

- [api/index.ts](api/index.ts)

HTTP client and interceptors:

- [lib/axios.ts](lib/axios.ts)

Behavior:

- Uses withCredentials for cookie auth
- Normalizes base URL from NEXT_PUBLIC_API_URL
- Auto handles 401 by clearing auth store and redirecting to login

Error normalization:

- [lib/errorHandler.ts](lib/errorHandler.ts)

## 10) Socket Layer

Socket provider:

- [context/SocketContext.tsx](context/SocketContext.tsx)

Responsibilities:

- Creates one socket client instance
- Reconnect strategy
- Exposes socket and isConnected
- Used by job progress and chat streaming flows

## 11) Folder Map

Top-level client folders:

- app: routes and layouts
- api: HTTP service layer
- components: UI and feature components
- context: React context providers (socket)
- hooks: reusable hooks (job status)
- lib: shared utilities (axios, cookie storage, error handling)
- store: Zustand slices
- types: shared TypeScript types
- public: static assets

## 12) End-to-End Mental Model

Think of the client as three UI states for a session:

1. No document
2. Processing document
3. Chat with ready document

The page [app/home/session/[sessionId]/page.tsx](app/home/session/[sessionId]/page.tsx) is the state orchestrator that chooses which component to show based on current session document status.

## 13) Troubleshooting

### App fails to start

Check:

- Node version
- npm install completed successfully
- Port 3400 availability

### Login works but API calls fail

Check:

- NEXT_PUBLIC_API_URL value
- Gateway running and CORS/cookie config

### Upload works but processing screen never updates

Check:

- Socket connection state from SocketContext
- Gateway Socket.IO server is running
- AI ingestion worker is running

### Chat submit works but no streamed answer

Check:

- Query worker is running
- Gateway query stream forwarding is active
- Session room join event is happening

### Unexpected redirect to login

Check:

- 401 responses in network tab
- Cookie credentials sent to API

## 14) Developer Onboarding Checklist

For a new contributor:

1. Run client locally and verify auth pages load.
2. Verify session list page can fetch sessions.
3. Upload a PDF and watch processing progress.
4. Ask a question and verify streaming answer.
5. Trigger a known error path and verify user-friendly message.

## 15) Suggested Next Improvements

- Add chat source citations UI using stream:sources payload
- Add optimistic UI for session actions
- Add integration tests for upload to chat path
- Add stronger connection status indicator for sockets

