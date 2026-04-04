import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthState, LoginDto, RegisterDto, ForgotPasswordDto, ResetPasswordDto } from '../../types/auth.types';
import { authApi } from '../../api';
import { cookieStorage } from '../../lib/cookieStorage';

interface AuthStore extends AuthState {
  login: (data: LoginDto) => Promise<void>;
  register: (data: RegisterDto) => Promise<void>;
  logout: () => Promise<void>;
  forgotPassword: (data: ForgotPasswordDto) => Promise<string>;
  resetPassword: (data: ResetPasswordDto) => Promise<string>;
  getProfile: () => Promise<void>;
  clearAuth: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.login(data);
          set({ 
            user: response.user, 
            token: response.token, 
            isAuthenticated: true,
            isLoading: false 
          });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.register(data);
          set({ 
            user: response.user, 
            token: response.token, 
            isAuthenticated: true,
            isLoading: false 
          });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        set({ isLoading: true, error: null });
        try {
          await authApi.logout();
          set({ 
            user: null, 
            token: null, 
            isAuthenticated: false,
            isLoading: false 
          });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      forgotPassword: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.forgotPassword(data);
          set({ isLoading: false });
          return response.message;
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      resetPassword: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.resetPassword(data);
          set({ isLoading: false });
          return response.message;
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      getProfile: async () => {
        set({ isLoading: true, error: null });
        try {
          const user = await authApi.getProfile();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      clearAuth: () => {
        set({ 
          user: null, 
          token: null, 
          isAuthenticated: false,
          error: null 
        });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      storage: cookieStorage,
      partialize: (state) => ({ 
        user: state.user, 
        token: state.token,
        isAuthenticated: state.isAuthenticated 
      }),
    }
  )
);
