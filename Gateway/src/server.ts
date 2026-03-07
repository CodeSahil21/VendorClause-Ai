import app from './app';
import { env } from './config';
import { connectDb, disconnectDb } from './lib/prisma';
import { connectRedis, redis } from './lib/redis';
import { validateMinioConnection, ensureBucket } from './lib/minio';

async function startServer() {
  try {
    await Promise.all([
      connectDb(),
      connectRedis(),
      validateMinioConnection()
    ]);
    
    // Ensure MinIO bucket exists
    await ensureBucket();
    
    console.log('✅ All services connected');

    const server = app.listen(env.PORT, () => {
      console.log(`
🚀 Gateway API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Environment: ${env.NODE_ENV}
🔗 Server:      http://localhost:${env.PORT}
❤️  Health:      http://localhost:${env.PORT}/health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      `);
    });

    const gracefulShutdown = async (signal: string) => {
      console.log(`\n${signal} received. Shutting down...`);
      server.close(async () => {
        try {
          await Promise.race([
            Promise.all([
              disconnectDb(),
              redis.isReady ? redis.disconnect() : Promise.resolve()
            ]),
            new Promise((_, reject) => 
              setTimeout(() => reject(new Error('Shutdown timeout')), 5000)
            )
          ]);
          console.log('🔌 Server closed gracefully');
        } catch (error) {
          console.warn('Shutdown warning:', error);
        } finally {
          process.exit(0);
        }
      });

      setTimeout(() => {
        console.error('Forced shutdown');
        process.exit(1);
      }, 10000);
    };

    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    process.on('SIGINT', () => gracefulShutdown('SIGINT'));
  } catch (error) {
    console.error('❌ Server startup failed:', error);
    process.exit(1);
  }
}

startServer();
