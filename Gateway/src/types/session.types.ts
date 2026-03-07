import { DocStatus, JobStatus, TaskType } from '@prisma/client';

export interface SessionResponse {
  id: string;
  userId: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface SessionWithDocuments extends SessionResponse {
  documents: DocumentResponse[];
}

export interface DocumentResponse {
  id: string;
  sessionId: string;
  userId: string;
  fileName: string;
  s3Url: string;
  status: DocStatus;
  createdAt: Date;
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
