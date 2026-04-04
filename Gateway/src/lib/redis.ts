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

redis.on('error', (err: Error) => {
  console.warn('⚠️  Redis connection failed:', err.message);
  console.log('📝 Application will continue without Redis caching');
});

redis.on('connect', () => console.log('✅ Redis connected'));
redis.on('disconnect', () => console.log('🔌 Redis disconnected'));

let initialized = false;
const localBlacklist = new Map<string, number>();

const isLocallyBlacklisted = (jti: string): boolean => {
  const expiresAt = localBlacklist.get(jti);
  if (!expiresAt) return false;
  if (expiresAt <= Date.now()) {
    localBlacklist.delete(jti);
    return false;
  }
  return true;
};

const rememberLocalBlacklist = (jti: string, ttlSec: number): void => {
  localBlacklist.set(jti, Date.now() + ttlSec * 1000);
};

export const connectRedis = async (): Promise<void> => {
  if (!initialized) {
    try {
      await redis.connect();
      initialized = true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.warn('⚠️  Redis connection failed:', message);
    }
  }
};

const sessionKey = (jti: string) => `auth:session:${jti}`;
const blacklistKey = (jti: string) => `auth:blacklist:${jti}`;
const resetTokenKey = (email: string) => `auth:reset:${email}`;

export const setSession = async (jti: string, data: unknown, ttlSec: number): Promise<void> => {
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

export const getSession = async <T = unknown>(jti: string): Promise<T | null> => {
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
  rememberLocalBlacklist(jti, ttlSec);
  try {
    if (!redis.isReady) return;
    await redis.set(blacklistKey(jti), '1', { EX: ttlSec });
  } catch (error) {
    console.warn('Redis blacklist failed:', error);
  }
};

export const isBlacklisted = async (jti: string): Promise<boolean> => {
  if (isLocallyBlacklisted(jti)) {
    return true;
  }

  try {
    if (!redis.isReady) {
      return false;
    }
    const exists = await redis.exists(blacklistKey(jti));
    return exists === 1;
  } catch (error) {
    return false;
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
