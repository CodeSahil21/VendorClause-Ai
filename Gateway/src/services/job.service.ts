import { prisma } from '../lib/prisma';
import { ApiError } from '../utils/apiError';

export class JobService {
  static async getJobById(jobId: string, userId: string) {
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

    // Verify user owns this job's document
    if (job.document.userId !== userId) {
      throw new ApiError(403, 'Unauthorized');
    }

    return job;
  }
}
