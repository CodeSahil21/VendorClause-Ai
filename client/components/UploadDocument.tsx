'use client';

import { useState } from 'react';
import { Upload, FileText, Loader2, XCircle } from 'lucide-react';
import { useDocumentStore } from '@/store';

interface UploadDocumentProps {
  sessionId: string;
  onUploadStart: (jobId: string) => void;
}

export default function UploadDocument({ sessionId, onUploadStart }: UploadDocumentProps) {
  const { uploadDocument, isUploading, error, clearError } = useDocumentStore();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      clearError();
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !sessionId) return;

    try {
      const result = await uploadDocument(sessionId, selectedFile);
      onUploadStart(result.job.id);
      setSelectedFile(null);
      const fileInput = document.getElementById('file-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload Document</h1>
        <p className="text-gray-600">Upload a PDF or DOCX file to start analyzing</p>

        <div className="mt-8">
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
                className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
                Upload Document
              </button>
            )}

            {isUploading && (
              <div className="mt-4 flex items-center justify-center gap-2 text-indigo-600">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-sm font-medium">Uploading...</span>
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
