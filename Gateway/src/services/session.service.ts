import { prisma } from '../lib/prisma';
import { ApiError } from '../utils/apiError';
import { CreateSessionDto, UpdateSessionDto } from '../schema/session.schema';
import { SessionResponse, SessionWithDocuments } from '../types/session.types';
import { CacheService } from '../lib/cache';

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
        documents: {
          orderBy: { createdAt: 'desc' }
        }
      }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }

    CacheService.setSessionWithDocuments(userId, sessionId, session, 300).catch(console.error);
    return session;
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
}
