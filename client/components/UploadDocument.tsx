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
  const [localError, setLocalError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  const isPdfFile = (file: File) => {
    const hasPdfMimeType = file.type === 'application/pdf';
    const hasPdfExtension = file.name.toLowerCase().endsWith('.pdf');
    return hasPdfMimeType || hasPdfExtension;
  };

  const setFileIfValid = (file: File) => {
    if (!isPdfFile(file)) {
      setLocalError('Only PDF files are supported');
      return;
    }

    setLocalError(null);
    setSelectedFile(file);
    clearError();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileIfValid(file);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      setFileIfValid(file);
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
      <div className="bg-slate-950/85 rounded-2xl shadow-xl shadow-black/30 border border-slate-700 p-6 sm:p-8 backdrop-blur-sm">
        <div className="mb-6">
          <p className="text-xs uppercase tracking-wide text-cyan-300 font-semibold">Ingestion</p>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-100 mt-1">Upload Document</h1>
          <p className="text-slate-300 mt-2">Upload a PDF to start legal analysis and document intelligence.</p>
        </div>

        <div>
          <div
            className={`border-2 border-dashed rounded-2xl p-8 sm:p-10 text-center bg-slate-900/60 transition-colors ${isDragActive ? 'border-cyan-400 bg-cyan-500/10' : 'border-slate-600 hover:border-cyan-500/60'}`}
            onDragOver={handleDragOver}
            onDragEnter={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Upload className="mx-auto h-12 w-12 text-cyan-300" />
            <div className="mt-4">
              <label htmlFor="file-upload" className="cursor-pointer">
                <span className="mt-2 block text-sm font-medium text-slate-100">
                  {selectedFile ? selectedFile.name : isDragActive ? 'Drop your PDF here' : 'Click to upload or drag and drop'}
                </span>
                <span className="mt-1 block text-xs text-slate-400">
                  PDF up to 50MB
                </span>
                <input
                  id="file-upload"
                  type="file"
                  className="hidden"
                  accept=".pdf"
                  onChange={handleFileChange}
                  disabled={isUploading}
                />
              </label>
            </div>

            {selectedFile && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <FileText className="h-5 w-5 text-cyan-300" />
                <span className="text-sm text-slate-200">{selectedFile.name}</span>
                <span className="text-xs text-slate-400">({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</span>
              </div>
            )}

            {selectedFile && !isUploading && (
              <button
                onClick={handleUpload}
                className="mt-5 px-6 py-2.5 bg-linear-to-r from-cyan-500 to-blue-600 text-white rounded-xl hover:from-cyan-600 hover:to-blue-700 transition-all shadow-lg hover:shadow-cyan-500/20">
                Upload Document
              </button>
            )}

            {isUploading && (
              <div className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-cyan-300">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-sm font-medium">Uploading...</span>
              </div>
            )}

            {(localError || error) && (
              <div className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-red-300">
                <XCircle className="h-5 w-5" />
                <span className="text-sm font-medium">{localError || error}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
