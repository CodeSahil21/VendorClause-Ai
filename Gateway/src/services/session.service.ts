import { prisma } from '../lib/prisma';
import { ApiError } from '../utils/apiError';
import { CreateSessionDto, UpdateSessionDto } from '../schema/session.schema';
import { SessionResponse, SessionWithDocuments } from '../types/session.types';
import { CacheService } from '../lib/cache';
import { redis } from '../lib/redis';
import { deriveStatusUpdatedAt, sanitizeDocument } from './document_sanitizer';

export class SessionService {
  static async createSession(userId: string, data: CreateSessionDto): Promise<SessionResponse> {
    const session = await prisma.chatSession.create({
      data: {
        userId,
        title: data.title
      }
    });

    CacheService.invalidateUserSessions(userId).catch(console.error);

    return session;
  }

  static async getUserSessions(
    userId: string,
    page: number = 1,
    limit: number = 20
  ): Promise<{ sessions: SessionResponse[]; total: number }> {
    const skip = (page - 1) * limit;

    const [sessions, total] = await Promise.all([
      prisma.chatSession.findMany({
        where: { userId },
        orderBy: { createdAt: 'desc' },
        skip,
        take: limit
      }),
      prisma.chatSession.count({ where: { userId } })
    ]);

    return { sessions, total };
  }

  static async getSessionById(sessionId: string, userId: string): Promise<SessionWithDocuments> {
    const cached = await CacheService.getSessionWithDocuments(userId, sessionId);
    if (cached) return cached;

    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId },
      include: {
        document: {
          include: {
            jobs: {
              orderBy: { createdAt: 'desc' },
              take: 1
            }
          }
        }
      }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }

    const enrichedSession: SessionWithDocuments = session.document
      ? {
          id: session.id,
          userId: session.userId,
          title: session.title,
          createdAt: session.createdAt,
          updatedAt: session.updatedAt,
          document: await sanitizeDocument({
            ...session.document,
            statusUpdatedAt: deriveStatusUpdatedAt(session.document.jobs, session.document.updatedAt),
          }),
        }
      : {
          id: session.id,
          userId: session.userId,
          title: session.title,
          createdAt: session.createdAt,
          updatedAt: session.updatedAt,
          document: null,
        };

    // Only cache sessions with documents in terminal states (READY/FAILED) or no document
    // Don't cache PENDING/PROCESSING - polling needs fresh DB reads for status transitions
    const isTransitional = enrichedSession.document &&
      (enrichedSession.document.status === 'PENDING' || enrichedSession.document.status === 'PROCESSING');

    if (!isTransitional) {
      CacheService.setSessionWithDocuments(userId, sessionId, enrichedSession, 300).catch(console.error);
    }
    
    return enrichedSession;
  }

  static async updateSession(sessionId: string, userId: string, data: UpdateSessionDto): Promise<SessionResponse> {
    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }

    const updated = await prisma.chatSession.update({
      where: { id: sessionId },
      data: { title: data.title }
    });

    CacheService.invalidateSessionCache(userId, sessionId).catch(console.error);

    return updated;
  }

  static async deleteSession(sessionId: string, userId: string): Promise<void> {
    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }

    await prisma.chatSession.delete({
      where: { id: sessionId }
    });

    CacheService.invalidateSessionCache(userId, sessionId).catch(console.error);
  }

  static async getChatHistory(sessionId: string, userId: string, limit: number = 50): Promise<{ role: string; content: string; createdAt: string }[]> {
    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId },
    });
    if (!session) throw new ApiError(404, 'Session not found');

    const messages = await prisma.message.findMany({
      where: { sessionId },
      orderBy: { createdAt: 'asc' },
      take: limit,
      select: { role: true, content: true, createdAt: true },
    });

    return messages.map(m => ({ role: m.role, content: m.content, createdAt: m.createdAt.toISOString() }));
  }

  static async dispatchQuery(sessionId: string, userId: string, question: string): Promise<{ queued: boolean; sessionId: string }> {
    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId },
      include: { document: true }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }
    if (!session.document) {
      throw new ApiError(400, 'No document linked to this session');
    }
    if (session.document.status !== 'READY') {
      throw new ApiError(400, `Document status is ${session.document.status}. Query is allowed only when READY.`);
    }
    if (!redis.isReady) {
      throw new ApiError(503, 'Redis is not ready');
    }
    const queryWorkerAlive = await redis.get('query-worker:heartbeat');
    if (!queryWorkerAlive) {
      throw new ApiError(503, 'Query service is unavailable. Please retry shortly.');
    }

    const payload = {
      question,
      sessionId,
      documentId: session.document.id,
      userId,
    };

    await redis.publish(`query:request:${sessionId}`, JSON.stringify(payload));
    return { queued: true, sessionId };
  }
}
