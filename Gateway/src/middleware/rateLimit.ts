import { Request, Response, NextFunction } from 'express';
import { redis } from '../lib/redis';
import { ApiResponse } from '../utils/apiResponse';

// In-memory rate limiting fallback (with periodic cleanup)
const memoryStore = new Map<string, { count: number; resetTime: number }>();

// Clean up expired entries every 5 minutes
const cleanupTimer: ReturnType<typeof setInterval> = setInterval(() => {
  const now = Date.now();
  for (const [key, record] of memoryStore) {
    if (now >= record.resetTime) {
      memoryStore.delete(key);
    }
  }
}, 5 * 60 * 1000);

const createRateLimit = (windowMs: number, max: number, keyPrefix: string) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const key = `${keyPrefix}:${req.ip}`;
    const now = Date.now();
    
    try {
      let count = 1;
      
      if (redis.isReady) {
        const current = await redis.incr(key);
        if (current === 1) {
          await redis.expire(key, Math.floor(windowMs / 1000));
        }
        count = current;
      } else {
        const record = memoryStore.get(key);
        if (record && now < record.resetTime) {
          count = record.count + 1;
          memoryStore.set(key, { count, resetTime: record.resetTime });
        } else {
          count = 1;
          memoryStore.set(key, { count, resetTime: now + windowMs });
        }
      }
      
      if (count > max) {
        res.status(429).json(new ApiResponse(429, null, 'Too many requests, please try again later'));
        return;
      }
      
      next();
    } catch (error) {
      console.warn('Rate limit error:', error);
      next();
    }
  };
};

export const authRateLimit = createRateLimit(15 * 60 * 1000, 20, 'auth_rate_limit');
export const apiRateLimit = createRateLimit(15 * 60 * 1000, 100, 'api_rate_limit');
export const uploadRateLimit = createRateLimit(60 * 60 * 1000, 10, 'upload_rate_limit');