import { prisma } from '../lib/prisma';
import { ApiError } from '../utils/apiError';
import { JobWithDocumentResponse } from '../types/session.types';

export class JobService {
  static async getJobById(jobId: string, userId: string): Promise<JobWithDocumentResponse> {
    const job = await prisma.job.findFirst({
      where: { id: jobId },
      include: {
        document: {
          select: {
            id: true,
            userId: true,
            fileName: true,
            status: true
          }
        }
      }
    });

    if (!job) {
      throw new ApiError(404, 'Job not found');
    }

    if (job.document.userId !== userId) {
      throw new ApiError(403, 'Unauthorized');
    }

    return job;
  }
}
