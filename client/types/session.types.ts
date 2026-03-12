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
  s3Url: string;
  status: string;
  createdAt: string;
  jobs?: JobInfo[];
}

// Session Types
export interface Session {
  id: string;
  userId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  document?: DocumentInfo | null;
}

// Request DTOs
export interface CreateSessionDto {
  title: string;
}

export interface UpdateSessionDto {
  title: string;
}

// Response Types
export interface SessionResponse {
  id: string;
  userId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  document?: DocumentInfo | null;
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

export interface DeleteSessionResponse {
  message: string;
}
