'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useSessionStore } from '@/store';

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const { currentSession, isLoading, getSessionById } = useSessionStore();

  useEffect(() => {
    if (sessionId) {
      getSessionById(sessionId);
    }
  }, [sessionId, getSessionById]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!currentSession) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Session not found</h2>
          <p className="mt-2 text-gray-600">The session you're looking for doesn't exist.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">{currentSession.title}</h1>
        <p className="text-gray-600">
          Created on {new Date(currentSession.createdAt).toLocaleDateString('en-US', {
            month: 'long',
            day: 'numeric',
            year: 'numeric'
          })}
        </p>
        <div className="mt-8">
          <p className="text-gray-500">Session content will be implemented here...</p>
        </div>
      </div>
    </div>
  );
}
