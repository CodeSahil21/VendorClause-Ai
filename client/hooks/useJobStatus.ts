import { useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';

interface JobStatusData {
  jobId: string;
  status: 'QUEUED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  documentId?: string;
  error?: string;
  timestamp: string;
}

export function useJobStatus(jobId: string | null) {
  const [status, setStatus] = useState<JobStatusData['status']>('QUEUED');
  const [error, setError] = useState<string | null>(null);
  const [socket, setSocket] = useState<Socket | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const socketUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000';
    const newSocket = io(socketUrl, {
      withCredentials: true
    });

    newSocket.on('connect', () => {
      console.log('✅ Socket connected:', newSocket.id);
      newSocket.emit('join', jobId);
    });

    newSocket.on('job:status', (data: JobStatusData) => {
      console.log('📢 Job status update:', data);
      setStatus(data.status);
      if (data.error) {
        setError(data.error);
      }
    });

    newSocket.on('disconnect', () => {
      console.log('🔌 Socket disconnected');
    });

    newSocket.on('connect_error', (err) => {
      console.error('❌ Socket connection error:', err);
    });

    setSocket(newSocket);

    return () => {
      if (newSocket) {
        newSocket.emit('leave', jobId);
        newSocket.disconnect();
      }
    };
  }, [jobId]);

  return { status, error, socket };
}
