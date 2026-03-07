import { AxiosError } from "axios";
import type { ApiErrorResponse } from "@/types/auth.types";

const sanitizeErrorMessage = (message: string): string => {
  if (message.includes('stack') || message.length > 150) {
    return 'An error occurred. Please try again.';
  }
  return message;
};

const handleAxiosError = (error: unknown, defaultMessage: string): string => {
  if (error instanceof AxiosError) {
    const errorData = error.response?.data as ApiErrorResponse | undefined;
    const statusCode = error.response?.status;
    
    // Extract message from backend ApiErrorResponse
    if (errorData?.message) {
      return sanitizeErrorMessage(errorData.message);
    }
    
    // Handle specific status codes
    if (statusCode === 401) return 'Invalid credentials';
    if (statusCode === 400) return 'Invalid request. Please check your input.';
    if (statusCode === 403) return 'Access denied';
    if (statusCode === 404) return 'Resource not found';
    if (statusCode === 500) return 'Server error. Please try again later.';
    if (statusCode === 503) return 'Service unavailable. Please try again later.';
    
    // Network errors
    if (!error.response) {
      return 'Network error. Please check your connection.';
    }
    
    return sanitizeErrorMessage(error.message || defaultMessage);
  }
  
  if (error instanceof Error) {
    return sanitizeErrorMessage(error.message || defaultMessage);
  }
  
  return defaultMessage;
};

export { handleAxiosError };
