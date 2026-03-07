import { create } from 'zustand';

interface UserState {
  preferences: Record<string, any>;
  setPreferences: (prefs: Record<string, any>) => void;
}

export const useUserStore = create<UserState>((set) => ({
  preferences: {},
  setPreferences: (prefs) => set({ preferences: prefs }),
}));
