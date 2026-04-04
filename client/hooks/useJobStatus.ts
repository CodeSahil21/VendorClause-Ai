import { useEffect, useState } from 'react';
import { useSocket } from '@/context/SocketContext';

interface JobStatusData {
  jobId: string;
  status: 'QUEUED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  documentId?: string;
  error?: string;
  timestamp: string;
}

interface JobProgressData {
  event: 'job:progress';
  jobId: string;
  documentId: string;
  status: 'IN_PROGRESS' | 'COMPLETED';
  progress: number;
  stage: string;
}

export function useJobStatus(jobId: string | null) {
  const { socket } = useSocket();
  const [status, setStatus] = useState<JobStatusData['status']>('QUEUED');
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [stage, setStage] = useState<string | null>(null);

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

      if (data.status === 'IN_PROGRESS') {
        setProgress(prev => (prev > 0 ? prev : 5));
      }
      if (data.status === 'COMPLETED') {
        setProgress(100);
      }
    };

    const handleJobProgress = (data: JobProgressData) => {
      if (data.jobId !== jobId) return;
      setProgress(data.progress);
      setStage(data.stage);
      if (data.documentId) setDocumentId(data.documentId);
    };

    socket.on('connect', handleConnect);
    socket.on('job:status', handleJobStatus);
    socket.on('job:progress', handleJobProgress);

    return () => {
      socket.emit('leave', jobId);
      socket.off('connect', handleConnect);
      socket.off('job:status', handleJobStatus);
      socket.off('job:progress', handleJobProgress);
    };
  }, [jobId, socket]);

  return { status, documentId, error, progress, stage };
}
