// Backend API Response Types
export interface User {
  id: string;
  email: string;
  name: string | null;
}

export interface UserProfileResponse {
  id: string;
  email: string;
  name: string | null;
}

export interface AuthResponse {
  user: {
    id: string;
    email: string;
    name: string | null;
    createdAt?: string;
  };
  token: string;
}

// Request DTOs (matching backend schemas)
export interface LoginDto {
  email: string;
  password: string;
}

export interface RegisterDto {
  email: string;
  password: string;
  name?: string;
}

export interface ForgotPasswordDto {
  email: string;
}

export interface ResetPasswordDto {
  email: string;
  token: string;
  password: string;
}

// Response Types
export interface ForgotPasswordResponse {
  message: string;
}

export interface LogoutResponse {
  message: string;
}

// Store State
export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

// API Error Response
export interface ApiErrorResponse {
  success: false;
  statusCode: number;
  message: string;
  errors?: any[];
  timestamp: string;
  path: string;
}

// API Success Response
export interface ApiSuccessResponse<T> {
  success: true;
  statusCode: number;
  data: T;
  message: string;
}
