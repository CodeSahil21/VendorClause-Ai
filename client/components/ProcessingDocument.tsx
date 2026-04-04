'use client';

import { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useJobStatus } from '@/hooks/useJobStatus';

interface ProcessingDocumentProps {
  jobId: string;
  onComplete: (documentId: string) => void;
  onError: (error: string) => void;
}

export default function ProcessingDocument({ jobId, onComplete, onError }: ProcessingDocumentProps) {
  const { status, documentId, error, progress, stage } = useJobStatus(jobId);

  useEffect(() => {
    if (status === 'COMPLETED' && documentId) {
      onComplete(documentId);
    } else if (status === 'FAILED' && error) {
      onError(error);
    }
  }, [status, documentId, error, onComplete, onError]);

  if (status === 'COMPLETED' || status === 'FAILED') {
    return null;
  }

  const getStatusMessage = () => {
    switch (status) {
      case 'QUEUED':
        return 'Queuing document for processing...';
      case 'IN_PROGRESS':
        return stage ? `Processing stage: ${stage.replaceAll('_', ' ')}` : 'Processing your document...';
      default:
        return 'Please wait...';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <Loader2 className="h-16 w-16 text-indigo-600 animate-spin" />
          <h2 className="mt-6 text-2xl font-semibold text-gray-900">Processing Document</h2>
          <p className="mt-3 text-center text-gray-600 text-base">
            {getStatusMessage()}
          </p>
          <div className="mt-8 w-full max-w-md">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.max(0, Math.min(100, progress || (status === 'QUEUED' ? 5 : 0)))}%` }}
              />
            </div>
          </div>
          <p className="mt-4 text-sm text-gray-500">
            Status: {status === 'QUEUED' ? 'Queued' : 'Processing'} ({Math.max(0, Math.min(100, progress || (status === 'QUEUED' ? 5 : 0)))}%)
          </p>
        </div>
      </div>
    </div>
  );
}
