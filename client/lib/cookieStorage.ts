import { PersistStorage } from 'zustand/middleware';

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

export const cookieStorage: PersistStorage<any> = {
  getItem: (name: string) => {
    const value = getCookie(name);
    return value ? JSON.parse(value) : null;
  },
  setItem: (name: string, value: any) => {
    setCookie(name, JSON.stringify(value), 7);
  },
  removeItem: (name: string) => {
    removeCookie(name);
  },
};
