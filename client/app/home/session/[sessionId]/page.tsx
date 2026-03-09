'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useSessionStore, useDocumentStore } from '@/store';
import { Upload, FileText, Loader2, CheckCircle, XCircle } from 'lucide-react';

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const { currentSession, isLoading, getSessionById } = useSessionStore();
  const { uploadDocument, isUploading, error, clearError } = useDocumentStore();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  useEffect(() => {
    if (sessionId) {
      getSessionById(sessionId);
    }
  }, [sessionId, getSessionById]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setUploadSuccess(false);
      clearError();
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !sessionId) return;

    try {
      await uploadDocument(sessionId, selectedFile);
      setUploadSuccess(true);
      setSelectedFile(null);
      // Reset file input
      const fileInput = document.getElementById('file-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };

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

        {/* Upload Section */}
        <div className="mt-8 border-t pt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Document</h2>
          
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-indigo-500 transition-colors">
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <div className="mt-4">
              <label htmlFor="file-upload" className="cursor-pointer">
                <span className="mt-2 block text-sm font-medium text-gray-900">
                  {selectedFile ? selectedFile.name : 'Click to upload or drag and drop'}
                </span>
                <span className="mt-1 block text-xs text-gray-500">
                  PDF or DOCX up to 50MB
                </span>
                <input
                  id="file-upload"
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx"
                  onChange={handleFileChange}
                  disabled={isUploading}
                />
              </label>
            </div>

            {selectedFile && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <FileText className="h-5 w-5 text-indigo-600" />
                <span className="text-sm text-gray-700">{selectedFile.name}</span>
                <span className="text-xs text-gray-500">({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</span>
              </div>
            )}

            {selectedFile && !isUploading && (
              <button
                onClick={handleUpload}
                className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                Upload Document
              </button>
            )}

            {isUploading && (
              <div className="mt-4 flex items-center justify-center gap-2 text-indigo-600">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-sm font-medium">Uploading...</span>
              </div>
            )}

            {uploadSuccess && (
              <div className="mt-4 flex items-center justify-center gap-2 text-green-600">
                <CheckCircle className="h-5 w-5" />
                <span className="text-sm font-medium">Document uploaded successfully!</span>
              </div>
            )}

            {error && (
              <div className="mt-4 flex items-center justify-center gap-2 text-red-600">
                <XCircle className="h-5 w-5" />
                <span className="text-sm font-medium">{error}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
