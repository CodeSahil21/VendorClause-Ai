import { Server as HTTPServer } from 'http';
import { Server, Socket } from 'socket.io';
import Redis from 'ioredis';
import { env } from '../config';

let io: Server | null = null;
let subscriber: Redis | null = null;

export function setupSocketIO(httpServer: HTTPServer): Server {
  io = new Server(httpServer, {
    cors: {
      origin: env.FRONTEND_URL,
      credentials: true,
      methods: ['GET', 'POST']
    }
  });

  subscriber = new Redis({
    host: env.REDIS_HOST,
    port: env.REDIS_PORT,
    password: env.REDIS_PASSWORD
  });

  // Subscribe to job status updates
  subscriber.psubscribe('job:*', (err) => {
    if (err) {
      console.error('❌ Failed to subscribe to Redis:', err);
    } else {
      console.log('✅ Subscribed to Redis pub/sub: job:*');
    }
  });

  // Handle Redis messages
  subscriber.on('pmessage', (pattern: string, channel: string, message: string) => {
    try {
      const jobId = channel.split(':')[1];
      const data = JSON.parse(message);
      
      // Emit to all clients in this job's room
      io?.to(jobId).emit('job:status', data);
      console.log(`📢 Broadcasted to room ${jobId}:`, data.status);
    } catch (error) {
      console.error('❌ Error processing Redis message:', error);
    }
  });

  // Handle client connections
  io.on('connection', (socket: Socket) => {
    console.log('🔌 Client connected:', socket.id);

    // Client joins room for specific job
    socket.on('join', (jobId: string) => {
      socket.join(jobId);
      console.log(`✅ Client ${socket.id} joined room: ${jobId}`);
    });

    // Client leaves room
    socket.on('leave', (jobId: string) => {
      socket.leave(jobId);
      console.log(`👋 Client ${socket.id} left room: ${jobId}`);
    });

    socket.on('disconnect', () => {
      console.log('🔌 Client disconnected:', socket.id);
    });
  });

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
