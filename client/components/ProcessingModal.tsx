'use client';

import { useEffect } from 'react';
import { useJobStatus } from '@/hooks/useJobStatus';
import { Loader2 } from 'lucide-react';

interface ProcessingModalProps {
  jobId: string;
  onComplete: (documentId: string) => void;
  onError: (error: string) => void;
}

export default function ProcessingModal({ jobId, onComplete, onError }: ProcessingModalProps) {
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
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-slate-950 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl border border-slate-700">
        <div className="flex flex-col items-center">
          <div className="h-14 w-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
            <Loader2 className="h-8 w-8 text-cyan-300 animate-spin" />
          </div>
          <h2 className="mt-4 text-xl font-semibold text-slate-100">Processing Document</h2>
          <p className="mt-2 text-center text-slate-300 text-sm">
            {getStatusMessage()}
          </p>
          <div className="mt-6 w-full">
            <div className="w-full bg-slate-800 rounded-full h-2.5 border border-slate-700">
              <div 
                className="bg-linear-to-r from-cyan-500 to-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.max(0, Math.min(100, progress || (status === 'QUEUED' ? 5 : 0)))}%` }}
              />
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-400">
            Status: {status === 'QUEUED' ? 'Queued' : 'Processing'} ({Math.max(0, Math.min(100, progress || (status === 'QUEUED' ? 5 : 0)))}%)
          </p>
        </div>
      </div>
    </div>
  );
}
