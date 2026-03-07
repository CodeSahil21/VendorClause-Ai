import { create } from 'zustand';
import type { Session, CreateSessionDto, UpdateSessionDto } from '../../types';
import { sessionApi } from '../../api';

interface SessionState {
  sessions: Session[];
  currentSession: Session | null;
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  } | null;
  isLoading: boolean;
  error: string | null;
}

interface SessionStore extends SessionState {
  createSession: (data: CreateSessionDto) => Promise<Session>;
  getUserSessions: (page?: number, limit?: number) => Promise<void>;
  getSessionById: (sessionId: string) => Promise<void>;
  updateSession: (sessionId: string, data: UpdateSessionDto) => Promise<Session>;
  deleteSession: (sessionId: string) => Promise<void>;
  setCurrentSession: (session: Session | null) => void;
  clearError: () => void;
}

export const useSessionStore = create<SessionStore>()((set) => ({
  sessions: [],
  currentSession: null,
  pagination: null,
  isLoading: false,
  error: null,

  createSession: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const session = await sessionApi.createSession(data);
      set((state) => ({ 
        sessions: [session, ...state.sessions],
        currentSession: session,
        isLoading: false 
      }));
      return session;
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  getUserSessions: async (page = 1, limit = 20) => {
    set({ isLoading: true, error: null });
    try {
      const response = await sessionApi.getUserSessions(page, limit);
      set({ 
        sessions: response.data, 
        pagination: response.pagination,
        isLoading: false 
      });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  getSessionById: async (sessionId) => {
    set({ isLoading: true, error: null });
    try {
      const session = await sessionApi.getSessionById(sessionId);
      set({ currentSession: session, isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  updateSession: async (sessionId, data) => {
    set({ isLoading: true, error: null });
    try {
      const updatedSession = await sessionApi.updateSession(sessionId, data);
      set((state) => ({
        sessions: state.sessions.map((s) => s.id === sessionId ? updatedSession : s),
        currentSession: state.currentSession?.id === sessionId ? updatedSession : state.currentSession,
        isLoading: false
      }));
      return updatedSession;
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  deleteSession: async (sessionId) => {
    set({ isLoading: true, error: null });
    try {
      await sessionApi.deleteSession(sessionId);
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== sessionId),
        currentSession: state.currentSession?.id === sessionId ? null : state.currentSession,
        isLoading: false
      }));
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  setCurrentSession: (session) => set({ currentSession: session }),

  clearError: () => set({ error: null }),
}));
