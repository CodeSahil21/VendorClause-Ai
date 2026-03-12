import { useEffect, useState } from 'react';
import { useSocket } from '@/context/SocketContext';

interface JobStatusData {
  jobId: string;
  status: 'QUEUED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  documentId?: string;
  error?: string;
  timestamp: string;
}

export function useJobStatus(jobId: string | null) {
  const { socket } = useSocket();
  const [status, setStatus] = useState<JobStatusData['status']>('QUEUED');
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId?.trim() || !socket) return;

    // Join the job room (socket may already be connected)
    if (socket.connected) {
      socket.emit('join', jobId);
    }

    // Re-join on reconnect
    const handleConnect = () => socket.emit('join', jobId);

    const handleJobStatus = (data: JobStatusData) => {
      if (data.jobId !== jobId) return;
      setStatus(data.status);
      if (data.documentId) setDocumentId(data.documentId);
      if (data.error) setError(data.error);
    };

    const handleComplete = (data: { documentId: string; jobId: string }) => {
      if (data.jobId !== jobId) return;
      setStatus('COMPLETED');
      setDocumentId(data.documentId);
    };

    socket.on('connect', handleConnect);
    socket.on('job:status', handleJobStatus);
    socket.on('ingestion:complete', handleComplete);

    return () => {
      socket.emit('leave', jobId);
      socket.off('connect', handleConnect);
      socket.off('job:status', handleJobStatus);
      socket.off('ingestion:complete', handleComplete);
    };
  }, [jobId, socket]);

  return { status, documentId, error };
}
