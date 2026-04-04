import { Client, BucketItem } from 'minio';
import { env } from '../config';

export const minioClient = new Client({
  endPoint: env.MINIO_ENDPOINT,
  port: env.MINIO_PORT,
  useSSL: env.MINIO_USE_SSL,
  accessKey: env.MINIO_ACCESS_KEY,
  secretKey: env.MINIO_SECRET_KEY
});

export const BUCKET_NAME = env.MINIO_BUCKET_NAME;

// Validate MinIO connection
export const validateMinioConnection = async (): Promise<void> => {
  try {
    await minioClient.listBuckets();
    console.log('✅ MinIO connection verified');
  } catch (error) {
    console.warn('⚠️  MinIO connection failed:', error);
    console.log('📝 File storage functionality will be limited');
  }
};

export const ensureBucket = async (): Promise<void> => {
  try {
    const exists = await minioClient.bucketExists(BUCKET_NAME);
    if (!exists) {
      await minioClient.makeBucket(BUCKET_NAME, 'us-east-1');
      console.log(`✅ Created MinIO bucket: ${BUCKET_NAME}`);
    }
  } catch (error) {
    console.error('Failed to ensure bucket exists:', error);
    throw new Error(`MinIO bucket setup failed: ${error}`);
  }
};

export const getPresignedUrlFromMinioUri = async (uri: string, expirySeconds: number = 3600): Promise<string | null> => {
  if (!uri.startsWith('minio://')) {
    return null;
  }

  const withoutScheme = uri.replace('minio://', '');
  const firstSlash = withoutScheme.indexOf('/');
  if (firstSlash <= 0 || firstSlash === withoutScheme.length - 1) {
    return null;
  }

  const bucket = withoutScheme.slice(0, firstSlash);
  const objectName = withoutScheme.slice(firstSlash + 1);
  return minioClient.presignedGetObject(bucket, objectName, expirySeconds);
};
