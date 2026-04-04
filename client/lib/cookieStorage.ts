import { PersistStorage, StorageValue } from 'zustand/middleware';

const getCookie = (name: string): string | null => {
  if (typeof document === 'undefined') return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
};

const setCookie = (name: string, value: string, days: number = 7) => {
  if (typeof document === 'undefined') return;
  const expires = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toUTCString();
  document.cookie = `${name}=${value}; expires=${expires}; path=/; SameSite=Strict`;
};

const removeCookie = (name: string) => {
  if (typeof document === 'undefined') return;
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
};

export const cookieStorage: PersistStorage<unknown> = {
  getItem: (name: string): StorageValue<unknown> | null => {
    const value = getCookie(name);
    if (!value) return null;
    try {
      return JSON.parse(value) as StorageValue<unknown>;
    } catch {
      removeCookie(name);
      return null;
    }
  },
  setItem: (name: string, value: StorageValue<unknown>) => {
    setCookie(name, JSON.stringify(value), 7);
  },
  removeItem: (name: string) => {
    removeCookie(name);
  },
};
