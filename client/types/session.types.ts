// Session Types
export interface Session {
  id: string;
  userId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
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
