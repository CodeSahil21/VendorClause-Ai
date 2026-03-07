'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store';

export default function RootPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  useEffect(() => {
    if (user) {
      router.push('/home');
    }
  }, [user, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600">
      <div className="text-center text-white">
        <h1 className="text-6xl font-bold mb-4">VendorClause AI</h1>
        <p className="text-xl">AI-Powered Vendor Service Agreement Platform</p>
      </div>
    </div>
  );
}
