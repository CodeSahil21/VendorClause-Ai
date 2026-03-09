'use client';

import { useJobStatus } from '@/hooks/useJobStatus';

interface DocumentUploadStatusProps {
  jobId: string;
  onComplete?: (documentId: string) => void;
  onError?: (error: string) => void;
}

export default function DocumentUploadStatus({ 
  jobId, 
  onComplete, 
  onError 
}: DocumentUploadStatusProps) {
  const { status, error } = useJobStatus(jobId);

  // Handle completion
  if (status === 'COMPLETED' && onComplete) {
    onComplete(jobId);
  }

  // Handle error
  if (status === 'FAILED' && onError && error) {
    onError(error);
  }

  const getStatusColor = () => {
    switch (status) {
      case 'QUEUED': return 'bg-gray-500';
      case 'IN_PROGRESS': return 'bg-blue-500';
      case 'COMPLETED': return 'bg-green-500';
      case 'FAILED': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'QUEUED': return '⏳';
      case 'IN_PROGRESS': return '⚙️';
      case 'COMPLETED': return '✅';
      case 'FAILED': return '❌';
      default: return '⏳';
    }
  };

  return (
    <div className="p-4 border rounded-lg">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{getStatusIcon()}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">Document Processing</span>
            <span className={`px-2 py-1 text-xs rounded text-white ${getStatusColor()}`}>
              {status}
            </span>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            Job ID: {jobId}
          </p>
          {error && (
            <p className="text-sm text-red-600 mt-2">
              Error: {error}
            </p>
          )}
        </div>
      </div>

      {status === 'IN_PROGRESS' && (
        <div className="mt-3">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-blue-500 h-2 rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
          <p className="text-xs text-gray-500 mt-1">Processing document...</p>
        </div>
      )}

      {status === 'COMPLETED' && (
        <div className="mt-3 p-2 bg-green-50 rounded text-sm text-green-700">
          ✅ Document is ready! You can now query it.
        </div>
      )}

      {status === 'FAILED' && (
        <div className="mt-3 p-2 bg-red-50 rounded text-sm text-red-700">
          ❌ Processing failed. Please try uploading again.
        </div>
      )}
    </div>
  );
}
