import { Server as HTTPServer } from 'http';
import { Server, Socket } from 'socket.io';
import Redis from 'ioredis';
import { env } from '../config';

let io: Server | null = null;
let subscriber: Redis | null = null;

export function setupSocketIO(httpServer: HTTPServer): Server {
  io = new Server(httpServer, {
    cors: {
      origin: [env.FRONTEND_URL, 'http://localhost:3000', 'http://localhost:3001'],
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
    retryStrategy: (times) => Math.min(times * 50, 2000)
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
  subscriber.psubscribe('job:*', (err, count) => {
    if (err) console.error('❌ Failed to psubscribe job:*:', err);
    else console.log(`✅ Subscribed to job:* (${count} subscriptions)`);
  });

  subscriber.subscribe('ingestion:complete', (err, count) => {
    if (err) console.error('❌ Failed to subscribe ingestion:complete:', err);
    else console.log(`✅ Subscribed to ingestion:complete (${count} subscriptions)`);
  });

  // Handle pattern messages (job:*)
  subscriber.on('pmessage', (_pattern: string, channel: string, message: string) => {
    try {
      const jobId = channel.split(':')[1];
      const data = JSON.parse(message);
      
      io?.to(jobId).emit('job:status', data);
      console.log(`📢 Job status ${jobId}:`, data.status);
    } catch (error) {
      console.error('❌ pmessage error:', error);
    }
  });

  // Handle direct messages (ingestion:complete) - only emit to relevant rooms
  subscriber.on('message', (_channel: string, message: string) => {
    try {
      const data = JSON.parse(message);

      // Emit to document room (for chat subscribers)
      if (data.documentId) {
        io?.to(data.documentId).emit('ingestion:complete', data);
      }
      // Also emit to job room (so useJobStatus receives completion)
      if (data.jobId) {
        io?.to(data.jobId).emit('ingestion:complete', data);
      }
      console.log(`📢 Ingestion complete:`, data.documentId);
    } catch (error) {
      console.error('❌ message error:', error);
    }
  });

  // Handle client connections
  io.on('connection', (socket: Socket) => {
    console.log('🔌 Client connected:', socket.id, 'from', socket.handshake.address);

    socket.on('join', (jobId: string) => {
      socket.join(jobId);
      console.log(`✅ Client ${socket.id} joined room: ${jobId}`);
    });

    socket.on('join-chat', (documentId: string) => {
      socket.join(documentId);
      console.log(`✅ Client ${socket.id} joined chat room: ${documentId}`);
    });

    socket.on('leave', (jobId: string) => {
      socket.leave(jobId);
      console.log(`👋 Client ${socket.id} left room: ${jobId}`);
    });

    socket.on('leave-chat', (documentId: string) => {
      socket.leave(documentId);
      console.log(`👋 Client ${socket.id} left chat room: ${documentId}`);
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
