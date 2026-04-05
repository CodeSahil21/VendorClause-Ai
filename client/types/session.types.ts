// Job Types
export interface JobInfo {
  id: string;
  documentId: string;
  taskType: string;
  status: string;
  error: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

// Document Types
export interface DocumentInfo {
  id: string;
  sessionId: string;
  userId: string;
  fileName: string;
  fileUrl: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  statusUpdatedAt?: string | null;
  jobs?: JobInfo[];
}

export interface JobWithDocumentInfo extends JobInfo {
  document: Pick<DocumentInfo, 'id' | 'userId' | 'fileName' | 'status'>;
}

// Request DTOs
export interface CreateSessionDto {
  title: string;
}

export interface UpdateSessionDto {
  title: string;
}

// Response Types — base (create/update/list)
export interface SessionResponse {
  id: string;
  userId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

// Response Type — getSessionById (includes document)
export interface SessionWithDocumentResponse extends SessionResponse {
  document: DocumentInfo | null;
}

export interface SessionsListResponse {
  data: SessionResponse[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export interface DocumentUploadResponse {
  document: DocumentInfo;
  job: JobInfo;
}

export interface QuerySessionResponse {
  queued: boolean;
  sessionId: string;
}

export interface ChatMessage {
  role: string;
  content: string;
  createdAt: string;
}
