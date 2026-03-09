import { create } from 'zustand';
import { documentApi } from '../../api';

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

interface DocumentWithJobs extends DocumentResponse {
  jobs: JobResponse[];
}

interface DocumentState {
  documents: DocumentResponse[];
  currentDocument: DocumentWithJobs | null;
  uploadProgress: number;
  isUploading: boolean;
  isLoading: boolean;
  error: string | null;
}

interface DocumentStore extends DocumentState {
  uploadDocument: (sessionId: string, file: File) => Promise<{ document: DocumentResponse; job: JobResponse }>;
  getDocument: (documentId: string) => Promise<void>;
  deleteDocument: (documentId: string) => Promise<void>;
  clearError: () => void;
  resetUpload: () => void;
}

export const useDocumentStore = create<DocumentStore>()((set) => ({
  documents: [],
  currentDocument: null,
  uploadProgress: 0,
  isUploading: false,
  isLoading: false,
  error: null,

  uploadDocument: async (sessionId, file) => {
    set({ isUploading: true, uploadProgress: 0, error: null });
    try {
      const result = await documentApi.uploadDocument(sessionId, file);
      set({ isUploading: false, uploadProgress: 100 });
      return result;
    } catch (error) {
      set({ error: (error as Error).message, isUploading: false, uploadProgress: 0 });
      throw error;
    }
  },

  getDocument: async (documentId) => {
    set({ isLoading: true, error: null });
    try {
      const document = await documentApi.getDocument(documentId);
      set({ currentDocument: document, isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  deleteDocument: async (documentId) => {
    set({ isLoading: true, error: null });
    try {
      await documentApi.deleteDocument(documentId);
      set((state) => ({
        documents: state.documents.filter((d) => d.id !== documentId),
        currentDocument: state.currentDocument?.id === documentId ? null : state.currentDocument,
        isLoading: false
      }));
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
  
  resetUpload: () => set({ uploadProgress: 0, isUploading: false, error: null }),
}));
