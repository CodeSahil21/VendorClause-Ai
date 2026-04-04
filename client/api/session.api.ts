import axiosInstance from "@/lib/axios";
import { handleAxiosError } from "@/lib/errorHandler";
import type { 
  CreateSessionDto, 
  UpdateSessionDto, 
  SessionResponse, 
  SessionWithDocumentResponse,
  SessionsListResponse,
  QuerySessionResponse
} from "@/types/session.types";
import type { ApiSuccessResponse } from "@/types/auth.types";

export const sessionApi = {
  createSession: async (data: CreateSessionDto): Promise<SessionResponse> => {
    try {
      const response = await axiosInstance.post<ApiSuccessResponse<SessionResponse>>('/sessions', data);
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to create session'));
    }
  },

  getUserSessions: async (page: number = 1, limit: number = 20): Promise<SessionsListResponse> => {
    try {
      const response = await axiosInstance.get<ApiSuccessResponse<SessionsListResponse>>('/sessions', {
        params: { page, limit }
      });
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to fetch sessions'));
    }
  },

  getSessionById: async (sessionId: string): Promise<SessionWithDocumentResponse> => {
    try {
      const response = await axiosInstance.get<ApiSuccessResponse<SessionWithDocumentResponse>>(`/sessions/${sessionId}`);
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to fetch session'));
    }
  },

  updateSession: async (sessionId: string, data: UpdateSessionDto): Promise<SessionResponse> => {
    try {
      const response = await axiosInstance.patch<ApiSuccessResponse<SessionResponse>>(`/sessions/${sessionId}`, data);
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to update session'));
    }
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    try {
      await axiosInstance.delete(`/sessions/${sessionId}`);
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to delete session'));
    }
  },

  querySession: async (sessionId: string, question: string): Promise<QuerySessionResponse> => {
    try {
      const response = await axiosInstance.post<ApiSuccessResponse<QuerySessionResponse>>(
        `/sessions/${sessionId}/query`,
        { question }
      );
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to submit query'));
    }
  },
};
