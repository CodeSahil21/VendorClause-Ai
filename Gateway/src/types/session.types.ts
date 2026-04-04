import { DocStatus, JobStatus, TaskType } from '@prisma/client';

export interface SessionResponse {
  id: string;
  userId: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface SessionWithDocuments extends SessionResponse {
  document: DocumentResponse | null;
}

export interface DocumentResponse {
  id: string;
  sessionId: string;
  userId: string;
  fileName: string;
  fileUrl: string | null;
  status: DocStatus;
  createdAt: Date;
  updatedAt: Date;
  statusUpdatedAt?: Date | null;
  jobs?: JobResponse[];
}

export interface DocumentUploadResponse {
  document: DocumentResponse;
  job: JobResponse;
}

export interface DocumentWithJobs extends DocumentResponse {
  jobs: JobResponse[];
}

export interface JobResponse {
  id: string;
  documentId: string;
  taskType: TaskType;
  status: JobStatus;
  error: string | null;
  startedAt: Date | null;
  completedAt: Date | null;
  createdAt: Date;
}

export interface JobWithDocumentResponse extends JobResponse {
  document: Pick<DocumentResponse, 'id' | 'userId' | 'fileName' | 'status'>;
}
