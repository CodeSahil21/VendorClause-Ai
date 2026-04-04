'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { useSessionStore, useDocumentStore } from '@/store';
import UploadDocument from '@/components/UploadDocument';
import ProcessingDocument from '@/components/ProcessingDocument';
import ChatDocument from '@/components/ChatDocument';

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const { currentSession, isLoading, getSessionById } = useSessionStore();
  const { setCurrentJobId } = useDocumentStore();
  const [currentJobId, setLocalJobId] = useState<string | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);

  // Derive the active jobId: use local state (from upload) or recover from session data (on revisit)
  const activeJobId = useMemo(() => {
    if (currentJobId) return currentJobId;
    // Recover jobId from session's document jobs (latest non-completed job)
    const jobs = currentSession?.document?.jobs;
    if (jobs && jobs.length > 0) {
      const activeJob = jobs.find(j => j.status === 'QUEUED' || j.status === 'IN_PROGRESS');
      if (activeJob) return activeJob.id;
    }
    return null;
  }, [currentJobId, currentSession?.document?.jobs]);

  useEffect(() => {
    if (sessionId) {
      getSessionById(sessionId).catch(() => {});
    }
  }, [sessionId, getSessionById]);

  // Poll for status updates while document is in a transitional state (fallback if Socket.IO misses events)
  useEffect(() => {
    const docStatus = currentSession?.document?.status;
    const isTransitional = docStatus === 'PENDING' || docStatus === 'PROCESSING' || !!currentJobId;
    if (!isTransitional) return;

    const interval = setInterval(() => {
      getSessionById(sessionId).catch(() => {});
    }, 3000);

    return () => clearInterval(interval);
  }, [sessionId, currentSession?.document?.status, currentJobId, getSessionById]);

  const handleUploadStart = useCallback((jobId: string) => {
    setLocalJobId(jobId);
    setCurrentJobId(jobId);
    // Re-fetch session to get the new document with PENDING status
    getSessionById(sessionId).catch(() => {});
  }, [setCurrentJobId, sessionId, getSessionById]);

  const handleProcessingComplete = useCallback((_documentId: string) => {
    setLocalJobId(null);
    getSessionById(sessionId).catch(() => {});
  }, [sessionId, getSessionById]);

  const handleProcessingError = useCallback((err: string) => {
    setLocalJobId(null);
    setProcessingError(err);
    // Re-fetch to get FAILED status from server
    getSessionById(sessionId).catch(() => {});
  }, [sessionId, getSessionById]);

  // Only show full-screen spinner on initial load (not during polling)
  if (isLoading && !currentSession) {
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

  // Show chat if document is ready
  if (currentSession.document?.status === 'READY') {
    return (
      <ChatDocument
        sessionId={sessionId}
        fileName={currentSession.document.fileName}
        fileUrl={currentSession.document.fileUrl}
      />
    );
  }

  // Show processing if document is PENDING, PROCESSING, or we just started an upload (currentJobId set)
  if (currentSession.document?.status === 'PROCESSING' || currentSession.document?.status === 'PENDING' || currentJobId) {
    return (
      <ProcessingDocument
        jobId={activeJobId || ''}
        onComplete={handleProcessingComplete}
        onError={handleProcessingError}
      />
    );
  }

  // Show error if document failed
  if (currentSession.document?.status === 'FAILED' || processingError) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="text-center">
            <div className="text-6xl mb-4">❌</div>
            <h2 className="text-2xl font-bold text-gray-900">Document Processing Failed</h2>
            <p className="mt-2 text-gray-600">
              {processingError || 'There was an error processing your document. Please try uploading again.'}
            </p>
            <button
              onClick={() => {
                setProcessingError(null);
                getSessionById(sessionId).catch(() => {});
              }}
              className="mt-6 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Show upload form (no document)
  return (
    <UploadDocument
      sessionId={sessionId}
      onUploadStart={handleUploadStart}
    />
  );
}
