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
      <div className="bg-slate-950/85 rounded-2xl shadow-xl shadow-black/30 border border-slate-700 p-8 sm:p-12 backdrop-blur-sm">
        <div className="flex flex-col items-center justify-center">
          <div className="h-18 w-18 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
            <Loader2 className="h-10 w-10 text-cyan-300 animate-spin" />
          </div>
          <h2 className="mt-6 text-2xl font-semibold text-slate-100">Processing Document</h2>
          <p className="mt-3 text-center text-slate-300 text-base">
            {getStatusMessage()}
          </p>
          <div className="mt-8 w-full max-w-md">
            <div className="w-full bg-slate-800 rounded-full h-2.5 border border-slate-700">
              <div 
                className="bg-linear-to-r from-cyan-500 to-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.max(0, Math.min(100, progress || (status === 'QUEUED' ? 5 : 0)))}%` }}
              />
            </div>
          </div>
          <p className="mt-4 text-sm text-slate-400">
            Status: {status === 'QUEUED' ? 'Queued' : 'Processing'} ({Math.max(0, Math.min(100, progress || (status === 'QUEUED' ? 5 : 0)))}%)
          </p>
        </div>
      </div>
    </div>
  );
}
