'use client';

import { Toaster } from 'react-hot-toast';

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      gutter={12}
      toastOptions={{
        duration: 3500,
        style: {
          background: 'rgba(2, 6, 23, 0.94)',
          color: '#e2e8f0',
          border: '1px solid rgba(34, 211, 238, 0.35)',
          borderRadius: '12px',
          boxShadow: '0 12px 30px rgba(0, 0, 0, 0.35)',
          backdropFilter: 'blur(8px)',
          fontWeight: '600',
        },
        success: {
          iconTheme: {
            primary: '#06b6d4',
            secondary: '#082f49',
          },
        },
        error: {
          iconTheme: {
            primary: '#ef4444',
            secondary: '#450a0a',
          },
        },
      }}
    />
  );
}
