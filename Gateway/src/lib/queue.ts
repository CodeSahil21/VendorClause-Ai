import { Queue } from 'bullmq';
import { env } from '../config';

export interface IngestionJobData {
  jobId: string;
  documentId: string;
  userId: string;
  pdfUrl: string;
}

let queueInstance: Queue<IngestionJobData> | null = null;

export const initQueue = async (): Promise<void> => {
  if (!queueInstance) {
    queueInstance = new Queue<IngestionJobData>('document-ingestion', {
      connection: {
        host: env.REDIS_HOST,
        port: env.REDIS_PORT,
        password: env.REDIS_PASSWORD
      },
      defaultJobOptions: {
        // Worker handles failure status updates explicitly and does not re-raise.
        attempts: 1,
        backoff: {
          type: 'exponential',
          delay: 2000
        },
        removeOnComplete: {
          count: 100,
          age: 24 * 3600
        },
        removeOnFail: {
          count: 1000
        }
      }
    });

    queueInstance.on('error', (err) => {
      console.warn('⚠️  BullMQ queue error:', err.message);
    });

    console.log('✅ BullMQ queue initialized');
  }
};

export const getQueue = (): Queue<IngestionJobData> => {
  if (!queueInstance) {
    throw new Error('Queue not initialized. Call initQueue() first.');
  }
  return queueInstance;
};

export const closeQueue = async (): Promise<void> => {
  if (queueInstance) {
    await queueInstance.close();
    queueInstance = null;
  }
};
