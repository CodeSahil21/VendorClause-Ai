import { redis } from './redis';
import { env } from '../config';
import { SessionResponse, SessionWithDocuments, DocumentWithJobs } from '../types/session.types';

const isDev = env.NODE_ENV === 'development';

export class CacheService {
  private static generateKey(...parts: string[]): string {
    return `cache:${parts.join(':')}`;
  }

  static async get<T>(prefix: string, id: string): Promise<T | null> {
    try {
      if (!redis.isReady) return null;
      
      const key = this.generateKey(prefix, id);
      const cached = await redis.get(key);
      
      if (cached) {
        if (isDev) console.log(`Cache HIT: ${key}`);
        return JSON.parse(cached) as T;
      }
      
      return null;
    } catch (error) {
      console.warn('Cache get failed:', error);
      return null;
    }
  }

  static async set<T>(prefix: string, id: string, data: T, ttlSec: number = 300): Promise<void> {
    try {
      if (!redis.isReady) return;
      
      const key = this.generateKey(prefix, id);
      await redis.set(key, JSON.stringify(data), { EX: ttlSec });
    } catch (error) {
      console.warn('Cache set failed:', error);
    }
  }

  static async del(prefix: string, id: string): Promise<void> {
    try {
      if (!redis.isReady) return;
      
      const key = this.generateKey(prefix, id);
      await redis.del(key);
    } catch (error) {
      console.warn('Cache del failed:', error);
    }
  }

  // Session-specific cache methods (scoped to userId)
  static async getUserSessions(userId: string): Promise<SessionResponse[] | null> {
    return this.get<SessionResponse[]>('user_sessions', userId);
  }

  static async setUserSessions(userId: string, sessions: SessionResponse[], ttl: number = 300): Promise<void> {
    return this.set('user_sessions', userId, sessions, ttl);
  }

  static async invalidateUserSessions(userId: string): Promise<void> {
    return this.del('user_sessions', userId);
  }

  // Session-with-documents cache (scoped to userId:sessionId)
  static async getSessionWithDocuments(userId: string, sessionId: string): Promise<SessionWithDocuments | null> {
    return this.get<SessionWithDocuments>('session_docs', `${userId}:${sessionId}`);
  }

  static async setSessionWithDocuments(userId: string, sessionId: string, session: SessionWithDocuments, ttl: number = 300): Promise<void> {
    return this.set('session_docs', `${userId}:${sessionId}`, session, ttl);
  }

  static async invalidateSessionWithDocuments(userId: string, sessionId: string): Promise<void> {
    return this.del('session_docs', `${userId}:${sessionId}`);
  }

  // Document cache (scoped to userId:documentId)
  static async getDocument(userId: string, documentId: string): Promise<DocumentWithJobs | null> {
    return this.get<DocumentWithJobs>('document', `${userId}:${documentId}`);
  }

  static async setDocument(userId: string, documentId: string, document: DocumentWithJobs, ttl: number = 600): Promise<void> {
    return this.set('document', `${userId}:${documentId}`, document, ttl);
  }

  static async invalidateDocument(userId: string, documentId: string): Promise<void> {
    return this.del('document', `${userId}:${documentId}`);
  }

  // Bulk invalidation
  static async invalidateSessionCache(userId: string, sessionId: string): Promise<void> {
    await Promise.all([
      this.invalidateSessionWithDocuments(userId, sessionId),
      this.invalidateUserSessions(userId)
    ]);
  }
}