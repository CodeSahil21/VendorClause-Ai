import { createClient } from 'redis';
import { env } from '../config';

export const redis = createClient({
  password: env.REDIS_PASSWORD,
  socket: env.REDIS_USE_TLS ? {
    host: env.REDIS_HOST,
    port: env.REDIS_PORT,
    tls: true,
    connectTimeout: 5000,
  } : {
    host: env.REDIS_HOST,
    port: env.REDIS_PORT,
    connectTimeout: 5000,
  },
});

redis.on('error', (err: any) => {
  console.warn('⚠️  Redis connection failed:', err.message);
  console.log('📝 Application will continue without Redis caching');
});

redis.on('connect', () => console.log('✅ Redis connected'));
redis.on('disconnect', () => console.log('🔌 Redis disconnected'));

let initialized = false;
export const connectRedis = async (): Promise<void> => {
  if (!initialized) {
    try {
      await redis.connect();
      initialized = true;
    } catch (error: any) {
      console.warn('⚠️  Redis connection failed:', error.message);
    }
  }
};

const sessionKey = (jti: string) => `auth:session:${jti}`;
const blacklistKey = (jti: string) => `auth:blacklist:${jti}`;
const resetTokenKey = (email: string) => `auth:reset:${email}`;

export const setSession = async (jti: string, data: Record<string, unknown>, ttlSec: number): Promise<void> => {
  try {
    if (!redis.isReady) {
      console.warn('Redis not ready, skipping session set');
      return;
    }
    await redis.set(sessionKey(jti), JSON.stringify(data), { EX: Math.max(ttlSec - 30, 1) });
  } catch (error) {
    console.warn('Redis setSession failed:', error);
  }
};

export const getSession = async <T = any>(jti: string): Promise<T | null> => {
  try {
    if (!redis.isReady) {
      return null;
    }
    const raw = await redis.get(sessionKey(jti));
    return raw ? JSON.parse(raw) as T : null;
  } catch (error) {
    return null;
  }
};

export const delSession = async (jti: string): Promise<void> => {
  try {
    if (!redis.isReady) return;
    await redis.del(sessionKey(jti));
  } catch (error) {
    console.warn('Redis delSession failed:', error);
  }
};

export const blacklist = async (jti: string, ttlSec: number): Promise<void> => {
  try {
    if (!redis.isReady) return;
    await redis.set(blacklistKey(jti), '1', { EX: ttlSec });
  } catch (error) {
    console.warn('Redis blacklist failed:', error);
  }
};

export const isBlacklisted = async (jti: string): Promise<boolean> => {
  try {
    if (!redis.isReady) {
      return true; // Fail closed — reject tokens when Redis is unavailable
    }
    const exists = await redis.exists(blacklistKey(jti));
    return exists === 1;
  } catch (error) {
    return true; // Fail closed on error
  }
};

export const setResetToken = async (email: string, token: string, ttlSec: number): Promise<void> => {
  try {
    await redis.set(resetTokenKey(email), token, { EX: ttlSec });
  } catch (error) {
    console.warn('Redis setResetToken failed:', error);
  }
};

export const getResetToken = async (email: string): Promise<string | null> => {
  try {
    return await redis.get(resetTokenKey(email));
  } catch (error) {
    return null;
  }
};

export const delResetToken = async (email: string): Promise<void> => {
  try {
    await redis.del(resetTokenKey(email));
  } catch (error) {
    console.warn('Redis delResetToken failed:', error);
  }
};
