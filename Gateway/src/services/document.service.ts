import { prisma } from '../lib/prisma';
import { minioClient, BUCKET_NAME } from '../lib/minio';
import { ApiError } from '../utils/apiError';
import { DocumentUploadResponse, DocumentWithJobs } from '../types/session.types';
import { CacheService } from '../lib/cache';
import { randomUUID } from 'crypto';
import { getQueue, initQueue, IngestionJobData } from '../lib/queue';
import { Queue } from 'bullmq';
import { DOCUMENT_CACHE_TTL_SECONDS, deriveStatusUpdatedAt, sanitizeDocument } from './document_sanitizer';

const getOrInitQueue = async (): Promise<Queue<IngestionJobData>> => {
  try {
    return getQueue();
  } catch (error) {
    if (error instanceof Error && error.message.includes('Queue not initialized')) {
      await initQueue();
      return getQueue();
    }
    throw error;
  }
};

export class DocumentService {
  static async uploadDocument(
    userId: string,
    sessionId: string,
    file: Express.Multer.File
  ): Promise<DocumentUploadResponse> {
    if (file.mimetype !== 'application/pdf') {
      throw new ApiError(400, 'Only PDF documents are supported for ingestion.');
    }

    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId },
      include: { document: true }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }

    if (session.document) {
      throw new ApiError(400, 'Session already has a document. Only one document per session is allowed.');
    }

    const fileExtension = file.originalname.split('.').pop()?.toLowerCase() || 'bin';
    const objectName = `${userId}/${sessionId}/${randomUUID()}.${fileExtension}`;

    await minioClient.putObject(BUCKET_NAME, objectName, file.buffer, file.size, {
      'Content-Type': file.mimetype
    });

    const s3Url = `minio://${BUCKET_NAME}/${objectName}`;

    const document = await prisma.document.create({
      data: {
        userId,
        sessionId,
        fileName: file.originalname,
        s3Url,
        status: 'PENDING'
      }
    });

    const job = await prisma.job.create({
      data: {
        documentId: document.id,
        taskType: 'FULL_INGESTION',
        status: 'QUEUED'
      }
    });

    const queueJobPayload = {
      jobId: job.id,
      documentId: document.id,
      userId,
      pdfUrl: s3Url
    };

    // Push job to Redis queue for Python worker.
    try {
      const queue = await getOrInitQueue();
      await queue.add('process-document', queueJobPayload);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      console.error('Failed to enqueue ingestion job:', error);
      throw new ApiError(503, `Ingestion queue is unavailable: ${detail}`);
    }

    CacheService.invalidateSessionCache(userId, sessionId).catch(console.error);

    const safeDocument = await sanitizeDocument({
      ...document,
      statusUpdatedAt: document.updatedAt,
    });

    return { document: safeDocument, job };
  }

  static async getDocumentById(documentId: string, userId: string): Promise<DocumentWithJobs> {
    const cached = await CacheService.getDocument(userId, documentId);
    if (cached) return cached;

    const document = await prisma.document.findFirst({
      where: { id: documentId, userId },
      include: {
        jobs: {
          orderBy: { createdAt: 'desc' }
        }
      }
    });

    if (!document) {
      throw new ApiError(404, 'Document not found');
    }

    const enrichedDocument = {
      ...document,
      statusUpdatedAt: deriveStatusUpdatedAt(document.jobs, document.updatedAt),
    };

    const safeDocument = await sanitizeDocument(enrichedDocument);
    const response: DocumentWithJobs = {
      ...safeDocument,
      jobs: document.jobs,
      statusUpdatedAt: enrichedDocument.statusUpdatedAt,
    };

    CacheService.setDocument(userId, documentId, response, DOCUMENT_CACHE_TTL_SECONDS).catch(console.error);
    return response;
  }

  static async deleteDocument(documentId: string, userId: string): Promise<void> {
    const document = await prisma.document.findFirst({
      where: { id: documentId, userId }
    });

    if (!document) {
      throw new ApiError(404, 'Document not found');
    }

    const objectName = document.s3Url.replace(`minio://${BUCKET_NAME}/`, '');
    await minioClient.removeObject(BUCKET_NAME, objectName);

    await prisma.document.delete({
      where: { id: documentId }
    });

    CacheService.invalidateDocument(userId, documentId).catch(console.error);
    CacheService.invalidateSessionCache(userId, document.sessionId).catch(console.error);
  }
}
