import axiosInstance from "@/lib/axios";
import { handleAxiosError } from "@/lib/errorHandler";
import type { ApiSuccessResponse } from "@/types/auth.types";
import type { DocumentInfo, DocumentUploadResponse } from "@/types/session.types";

export const documentApi = {
  uploadDocument: async (sessionId: string, file: File): Promise<DocumentUploadResponse> => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('sessionId', sessionId);

      const response = await axiosInstance.post<ApiSuccessResponse<DocumentUploadResponse>>(
        '/documents/upload',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to upload document'));
    }
  },

  getDocument: async (documentId: string): Promise<DocumentInfo> => {
    try {
      const response = await axiosInstance.get<ApiSuccessResponse<DocumentInfo>>(
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
