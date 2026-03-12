'use client';

import { useState, useEffect } from 'react';
import { Send, FileText, Download, ExternalLink } from 'lucide-react';
import { useSocket } from '@/context/SocketContext';

interface ChatDocumentProps {
  documentId: string;
  fileName: string;
  s3Url: string;
}

const transformS3Url = (url: string): string => {
  if (!url) return '';
  if (url.startsWith('minio://')) {
    const path = url.replace('minio://', '');
    return `http://localhost:9000/${path}`;
  }
  if (url.startsWith('s3://')) {
    const path = url.replace('s3://', '');
    return `http://localhost:9000/${path}`;
  }
  return url;
};

export default function ChatDocument({ documentId, fileName, s3Url }: ChatDocumentProps) {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { socket } = useSocket();
  const pdfUrl = transformS3Url(s3Url);

  useEffect(() => {
    if (!socket) return;

    if (socket.connected) {
      socket.emit('join-chat', documentId);
    }

    const handleConnect = () => socket.emit('join-chat', documentId);

    const handleResponse = (data: { response: string; citations?: string[] }) => {
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      setIsLoading(false);
    };

    const handleError = (data: { error: string }) => {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${data.error}` }]);
      setIsLoading(false);
    };

    socket.on('connect', handleConnect);
    socket.on('query:response', handleResponse);
    socket.on('query:error', handleError);

    return () => {
      socket.emit('leave-chat', documentId);
      socket.off('connect', handleConnect);
      socket.off('query:response', handleResponse);
      socket.off('query:error', handleError);
    };
  }, [documentId, socket]);

  const handleSendMessage = () => {
    if (!input.trim() || !socket?.connected) return;

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    socket.emit('query:document', {
      documentId,
      query: userMessage
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Chat with Document</h1>
        <p className="text-gray-600 mt-1">Document: {fileName}</p>
      </div>

      <div className="grid grid-cols-2 gap-6 h-[calc(100vh-200px)]">
        {/* PDF Viewer */}
        <div className="border border-gray-200 rounded-lg overflow-hidden flex flex-col bg-gray-50">
          {/* PDF Toolbar */}
          <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-indigo-600" />
              <span className="font-medium text-gray-900 truncate text-sm">{fileName}</span>
            </div>
            <div className="flex gap-2">
              <a
                href={pdfUrl}
                download={fileName}
                className="p-2 hover:bg-gray-100 rounded transition-colors"
                title="Download PDF"
              >
                <Download className="h-4 w-4 text-gray-600" />
              </a>
              <a
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 hover:bg-gray-100 rounded transition-colors"
                title="Open in new tab"
              >
                <ExternalLink className="h-4 w-4 text-gray-600" />
              </a>
            </div>
          </div>

          {/* PDF Content - Using embed for better compatibility */}
          <div className="flex-1 overflow-auto bg-gray-100">
            {pdfUrl ? (
              <embed
                src={pdfUrl}
                type="application/pdf"
                className="w-full h-full"
                title="Document Preview"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                No PDF URL available
              </div>
            )}
          </div>
        </div>

        {/* Chat Interface */}
        <div className="border border-gray-200 rounded-lg overflow-hidden flex flex-col bg-white">
          <div className="bg-white border-b border-gray-200 p-4">
            <h3 className="font-semibold text-gray-900">Ask Questions</h3>
            <p className="text-xs text-gray-500 mt-1">Query your document using natural language</p>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-center">
                <div>
                  <p className="text-gray-500">No messages yet</p>
                  <p className="text-xs text-gray-400 mt-1">Ask a question about the document</p>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-xs px-4 py-2 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="text-sm">{msg.content}</p>
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Ask a question..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={isLoading}
              />
              <button
                onClick={handleSendMessage}
                disabled={isLoading || !input.trim()}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
