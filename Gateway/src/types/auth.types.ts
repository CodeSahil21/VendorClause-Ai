export interface UserResponse {
  id: string;
  email: string;
  name: string | null;
  createdAt: Date;
}

export interface AuthResponse {
  user: UserResponse;
  token: string;
}

export interface ForgotPasswordResponse {
  message: string;
}
