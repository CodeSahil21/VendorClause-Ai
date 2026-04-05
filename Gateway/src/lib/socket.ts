import { Server as HTTPServer } from 'http';
import { Server, Socket } from 'socket.io';
import Redis from 'ioredis';
import { env } from '../config';

type JobStatus = 'QUEUED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
type QueryStreamEvent = 'stream:token' | 'stream:done' | 'stream:error' | 'stream:sources';

interface JobStatusPayload {
  jobId: string;
  status: JobStatus;
  timestamp: string;
  documentId?: string;
  error?: string;
}

interface JobProgressPayload {
  event: 'job:progress';
  jobId: string;
  documentId: string;
  status: 'IN_PROGRESS' | 'COMPLETED';
  progress: number;
  stage: string;
}

const isJobProgressPayload = (data: JobStatusPayload | JobProgressPayload): data is JobProgressPayload => {
  return (data as JobProgressPayload).event === 'job:progress';
};

interface StreamTokenPayload {
  token: string;
}

interface StreamDonePayload {
  message: string;
  sources?: Array<{ chunk_id?: string; clause_type?: string; importance?: number }>;
}

interface StreamErrorPayload {
  message: string;
}

interface StreamSourcesPayload {
  sources: Array<{ chunk_id?: string; clause_type?: string; importance?: number }>;
}

type QueryStreamPayload = StreamTokenPayload | StreamDonePayload | StreamErrorPayload | StreamSourcesPayload;

interface QueryStreamMessage {
  event: QueryStreamEvent;
  payload: QueryStreamPayload;
}

let io: Server | null = null;
let subscriber: Redis | null = null;
// Room contract:
// - jobId room (`join`) receives `job:status` only.
// - sessionId room (`join-session`) receives `stream:*` query events.
const socketCorsOrigins = [
  env.FRONTEND_URL,
  ...(env.CORS_ORIGINS ? env.CORS_ORIGINS.split(',').map((origin) => origin.trim()).filter(Boolean) : []),
];

export function setupSocketIO(httpServer: HTTPServer): Server {
  io = new Server(httpServer, {
    cors: {
      origin: socketCorsOrigins,
      credentials: true,
      methods: ['GET', 'POST']
    },
    transports: ['websocket', 'polling'],
    pingInterval: 25000,
    pingTimeout: 60000
  });

  subscriber = new Redis({
    host: env.REDIS_HOST,
    port: env.REDIS_PORT,
    password: env.REDIS_PASSWORD,
    retryStrategy: (times: number) => Math.min(times * 50, 2000)
  });

  subscriber.on('error', (err) => {
    console.error('❌ Redis subscriber error:', err);
  });

  subscriber.on('connect', () => {
    console.log('✅ Redis subscriber connected');
  });

  io.engine.on('connection_error', (err) => {
    console.error('❌ Socket.IO connection error:', err);
  });

  // Subscribe to both channels
  subscriber.psubscribe('job:*', (err: Error | null, count: number) => {
    if (err) console.error('❌ Failed to psubscribe job:*:', err);
    else console.log(`✅ Subscribed to job:* (${count} subscriptions)`);
  });

  subscriber.psubscribe('query:stream:*', (err: Error | null, count: number) => {
    if (err) console.error('❌ Failed to psubscribe query:stream:*:', err);
    else console.log(`✅ Subscribed to query:stream:* (${count} subscriptions)`);
  });

  // Handle pattern messages (job:*)
  subscriber.on('pmessage', (_pattern: string, channel: string, message: string) => {
    try {
      if (channel.startsWith('job:')) {
        const jobId = channel.split(':')[1];
        const data = JSON.parse(message) as JobStatusPayload | JobProgressPayload;

        if (isJobProgressPayload(data)) {
          io?.to(jobId).emit('job:progress', data);
          console.log(`📢 Job progress ${jobId}:`, data.progress, data.stage);
        } else {
          io?.to(jobId).emit('job:status', data);
          console.log(`📢 Job status ${jobId}:`, (data as JobStatusPayload).status);
        }
        return;
      }

      if (channel.startsWith('query:stream:')) {
        const sessionId = channel.split(':')[2];
        const data = JSON.parse(message) as QueryStreamMessage;
        if (data?.event) {
          io?.to(sessionId).emit(data.event, data.payload);
        }
        return;
      }
    } catch (error) {
      console.error('❌ pmessage error:', error);
    }
  });

  // Handle client connections
  io.on('connection', (socket: Socket) => {
    console.log('🔌 Client connected:', socket.id, 'from', socket.handshake.address);

    socket.on('join', (jobId: string) => {
      socket.join(jobId);
      console.log(`✅ Client ${socket.id} joined room: ${jobId}`);
    });

    socket.on('join-session', (sessionId: string) => {
      socket.join(sessionId);
      console.log(`✅ Client ${socket.id} joined session room: ${sessionId}`);
    });

    socket.on('leave', (jobId: string) => {
      socket.leave(jobId);
      console.log(`👋 Client ${socket.id} left room: ${jobId}`);
    });

    socket.on('leave-session', (sessionId: string) => {
      socket.leave(sessionId);
      console.log(`👋 Client ${socket.id} left session room: ${sessionId}`);
    });

    socket.on('disconnect', (reason) => {
      console.log('🔌 Client disconnected:', socket.id, 'reason:', reason);
    });

    socket.on('error', (error) => {
      console.error('❌ Socket error:', socket.id, error);
    });
  });

  console.log(`✅ Socket.IO initialized on port ${env.PORT}`);
  return io;
}

export function getIO(): Server | null {
  return io;
}

export async function closeSocketIO(): Promise<void> {
  if (subscriber) {
    await subscriber.quit();
    subscriber = null;
  }
  if (io) {
    io.close();
    io = null;
  }
  console.log('🔌 Socket.IO closed');
}
