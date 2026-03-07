import axiosInstance from "@/lib/axios";
import { handleAxiosError } from "@/lib/errorHandler";
import type { 
  AuthResponse, 
  LoginDto, 
  RegisterDto, 
  ForgotPasswordDto, 
  ResetPasswordDto,
  ForgotPasswordResponse,
  UserProfileResponse,
  ApiSuccessResponse
} from "@/types/auth.types";

export const authApi = {
  register: async (data: RegisterDto): Promise<AuthResponse> => {
    try {
      const response = await axiosInstance.post<ApiSuccessResponse<{ user: UserProfileResponse }>>('/auth/register', data);
      return { user: response.data.data.user, token: '' };
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Registration failed'));
    }
  },

  login: async (data: LoginDto): Promise<AuthResponse> => {
    try {
      const response = await axiosInstance.post<ApiSuccessResponse<{ user: UserProfileResponse }>>('/auth/login', data);
      return { user: response.data.data.user, token: '' };
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Login failed'));
    }
  },

  logout: async (): Promise<void> => {
    try {
      await axiosInstance.post('/auth/logout');
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Logout failed'));
    }
  },

  forgotPassword: async (data: ForgotPasswordDto): Promise<ForgotPasswordResponse> => {
    try {
      const response = await axiosInstance.post<ApiSuccessResponse<ForgotPasswordResponse>>('/auth/forgot-password', data);
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to send reset email'));
    }
  },

  resetPassword: async (data: ResetPasswordDto): Promise<ForgotPasswordResponse> => {
    try {
      const response = await axiosInstance.post<ApiSuccessResponse<ForgotPasswordResponse>>('/auth/reset-password', data);
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Password reset failed'));
    }
  },

  getProfile: async (): Promise<UserProfileResponse> => {
    try {
      const response = await axiosInstance.get<ApiSuccessResponse<UserProfileResponse>>('/auth/profile');
      return response.data.data;
    } catch (error) {
      throw new Error(handleAxiosError(error, 'Failed to fetch profile'));
    }
  },
};
