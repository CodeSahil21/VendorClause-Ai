import { prisma } from '../lib/prisma';
import { minioClient, BUCKET_NAME } from '../lib/minio';
import { ApiError } from '../utils/apiError';
import { DocumentUploadResponse, DocumentWithJobs } from '../types/session.types';
import { CacheService } from '../lib/cache';
import { v4 as uuidv4 } from 'uuid';
import { getQueue } from '../lib/queue';

export class DocumentService {
  static async uploadDocument(
    userId: string,
    sessionId: string,
    file: Express.Multer.File
  ): Promise<DocumentUploadResponse> {
    const session = await prisma.chatSession.findFirst({
      where: { id: sessionId, userId }
    });

    if (!session) {
      throw new ApiError(404, 'Session not found');
    }

    const fileExtension = file.originalname.split('.').pop()?.toLowerCase() || 'bin';
    const objectName = `${userId}/${sessionId}/${uuidv4()}.${fileExtension}`;

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

    // Push job to Redis queue for Python worker
    await getQueue().add('process-document', {
      jobId: job.id,
      documentId: document.id,
      userId,
      pdfUrl: s3Url
    });

    CacheService.invalidateSessionWithDocuments(userId, sessionId).catch(console.error);

    return { document, job };
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

    CacheService.setDocument(userId, documentId, document, 600).catch(console.error);
    return document;
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
    CacheService.invalidateSessionWithDocuments(userId, document.sessionId).catch(console.error);
  }
}
