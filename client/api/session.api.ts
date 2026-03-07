import axiosInstance from "@/lib/axios";
import { handleAxiosError } from "@/lib/errorHandler";
import type { 
  CreateSessionDto, 
  UpdateSessionDto, 
  SessionResponse, 
  SessionsListResponse,
  DeleteSessionResponse
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

  getSessionById: async (sessionId: string): Promise<SessionResponse> => {
    try {
      const response = await axiosInstance.get<ApiSuccessResponse<SessionResponse>>(`/sessions/${sessionId}`);
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

  deleteSession: async (sessionId: string): Promise<DeleteSessionResponse> => {
    try {
      const response = await axiosInstance.delete<ApiSuccessResponse<DeleteSessionResponse>>(`/sessions/${sessionId}`);
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to delete session'));
    }
  },
};
