'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store';
import { useRouter, usePathname } from 'next/navigation';

const publicPaths = ['/login', '/register', '/forgot-password', '/reset-password'];

export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const [isHydrated, setIsHydrated] = useState(false);
  const { isAuthenticated, getProfile } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const isPublicPath = publicPaths.some(path => pathname.startsWith(path));

  useEffect(() => {
    const unsubscribe = useAuthStore.persist.onFinishHydration(() => {
      setIsHydrated(true);
    });

    if (useAuthStore.persist.hasHydrated()) {
      setIsHydrated(true);
    }

    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!isHydrated) return;

    const initAuth = async () => {
      if (isAuthenticated) {
        try {
          await getProfile();
          if (isPublicPath) {
            router.replace('/');
          }
        } catch (error) {
          // Handled by axios interceptor
        }
      } else if (!isPublicPath) {
        router.replace('/login');
      }
    };

    initAuth();
  }, [isHydrated, isAuthenticated, isPublicPath, pathname]);

  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
