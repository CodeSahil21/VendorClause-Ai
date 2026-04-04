import { getPresignedUrlFromMinioUri } from '../lib/minio';
import { DocumentResponse, JobResponse } from '../types/session.types';

export const DOCUMENT_CACHE_TTL_SECONDS = 600;
export const DOCUMENT_PRESIGNED_URL_TTL_SECONDS = 3600;

if (DOCUMENT_CACHE_TTL_SECONDS >= DOCUMENT_PRESIGNED_URL_TTL_SECONDS) {
	throw new Error('DOCUMENT_CACHE_TTL_SECONDS must be smaller than DOCUMENT_PRESIGNED_URL_TTL_SECONDS');
}

export type DocumentWithInternalUrl = Omit<DocumentResponse, 'fileUrl'> & { s3Url: string };

export const deriveStatusUpdatedAt = (jobs: JobResponse[] | undefined, fallback: Date): Date => {
	const latestJob = jobs?.[0];
	if (!latestJob) return fallback;
	return latestJob.completedAt ?? latestJob.startedAt ?? latestJob.createdAt;
};

export const sanitizeDocument = async (doc: DocumentWithInternalUrl): Promise<DocumentResponse> => {
	const fileUrl = await getPresignedUrlFromMinioUri(doc.s3Url, DOCUMENT_PRESIGNED_URL_TTL_SECONDS);
	const { s3Url: _s3Url, ...safeDoc } = doc;
	return {
		...safeDoc,
		fileUrl,
	};
};
