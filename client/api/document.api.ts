import axiosInstance from "@/lib/axios";
import { handleAxiosError } from "@/lib/errorHandler";
import type { ApiSuccessResponse } from "@/types/auth.types";

interface DocumentResponse {
  id: string;
  sessionId: string;
  userId: string;
  fileName: string;
  s3Url: string;
  status: string;
  createdAt: string;
}

interface JobResponse {
  id: string;
  documentId: string;
  taskType: string;
  status: string;
  error: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

interface DocumentUploadResponse {
  document: DocumentResponse;
  job: JobResponse;
}

interface DocumentWithJobs extends DocumentResponse {
  jobs: JobResponse[];
}

export const documentApi = {
  uploadDocument: async (sessionId: string, file: File): Promise<DocumentUploadResponse> => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('sessionId', sessionId);

      const response = await axiosInstance.post<ApiSuccessResponse<DocumentUploadResponse>>(
        '/documents/upload',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to upload document'));
    }
  },

  getDocument: async (documentId: string): Promise<DocumentWithJobs> => {
    try {
      const response = await axiosInstance.get<ApiSuccessResponse<DocumentWithJobs>>(
        `/documents/${documentId}`
      );
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to fetch document'));
    }
  },

  deleteDocument: async (documentId: string): Promise<void> => {
    try {
      await axiosInstance.delete(`/documents/${documentId}`);
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to delete document'));
    }
  },
};
