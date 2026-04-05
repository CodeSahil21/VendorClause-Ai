'use client';

import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, FileText, Download, ExternalLink } from 'lucide-react';
import { useSocket } from '@/context/SocketContext';
import { sessionApi } from '@/api';

interface ChatDocumentProps {
  sessionId: string;
  fileName: string;
  fileUrl: string | null;
}

export default function ChatDocument({ sessionId, fileName, fileUrl }: ChatDocumentProps) {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const streamingTextRef = useRef('');
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const { socket } = useSocket();
  const pdfUrl = fileUrl || '';

  const scrollToLatest = () => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  };

  // Load chat history on mount
  useEffect(() => {
    sessionApi.getChatHistory(sessionId).then(history => {
      setMessages(history.map(m => ({
        role: m.role === 'USER' ? 'user' : 'assistant',
        content: m.content,
      })));
    }).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    if (!socket) return;

    if (socket.connected) {
      socket.emit('join-session', sessionId);
    }

    const handleConnect = () => socket.emit('join-session', sessionId);

    const handleToken = (data: { token?: string }) => {
      if (!data?.token) return;
      streamingTextRef.current += data.token;
      setStreamingText(prev => prev + data.token);
    };

    const handleDone = (data: { message?: string }) => {
      const finalText = (data?.message || streamingTextRef.current || '').trim();
      streamingTextRef.current = '';
      if (finalText) {
        setMessages(prev => [...prev, { role: 'assistant', content: finalText }]);
      }
      setStreamingText('');
      setIsLoading(false);
    };

    const handleSources = (_data: { sources?: Array<{ chunk_id?: string }> }) => {
      // Sources are emitted for citations UI; no-op for now to avoid breaking flow.
    };

    const handleError = (data: { message?: string; error?: string }) => {
      const errorText = data?.message || data?.error || 'Unknown error';
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${errorText}` }]);
      setStreamingText('');
      setIsLoading(false);
    };

    socket.on('connect', handleConnect);
    socket.on('stream:token', handleToken);
    socket.on('stream:done', handleDone);
    socket.on('stream:sources', handleSources);
    socket.on('stream:error', handleError);

    return () => {
      socket.emit('leave-session', sessionId);
      socket.off('connect', handleConnect);
      socket.off('stream:token', handleToken);
      socket.off('stream:done', handleDone);
      socket.off('stream:sources', handleSources);
      socket.off('stream:error', handleError);
    };
  }, [sessionId, socket]);

  useEffect(() => {
    scrollToLatest();
  }, [messages, streamingText, isLoading]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = input;
    setInput('');
    streamingTextRef.current = '';
    setStreamingText('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      await sessionApi.querySession(sessionId, userMessage);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${(error as Error).message}` },
      ]);
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 rounded-2xl border border-cyan-500/25 bg-slate-950/75 px-4 py-3 shadow-lg shadow-black/20 backdrop-blur-sm">
        <p className="text-[11px] sm:text-xs uppercase tracking-wide text-cyan-300 font-semibold">Document Workspace</p>
        <p className="text-sm text-slate-300 mt-2 truncate">
          <span className="font-medium text-slate-100">Document:</span> {fileName}
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 h-auto xl:h-[calc(100vh-200px)]">
        {/* PDF Viewer */}
        <div className="xl:col-span-5 border border-slate-700 rounded-2xl overflow-hidden flex flex-col bg-slate-900/80 shadow-xl shadow-black/20 min-h-105">
          {/* PDF Toolbar */}
          <div className="bg-slate-950/90 border-b border-slate-700 p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-cyan-300" />
              <span className="font-medium text-slate-100 truncate text-sm">{fileName}</span>
            </div>
            <div className="flex gap-2">
              <a
                href={pdfUrl}
                download={fileName}
                className="p-2 hover:bg-slate-800 rounded transition-colors"
                title="Download PDF"
              >
                <Download className="h-4 w-4 text-slate-300" />
              </a>
              <a
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 hover:bg-slate-800 rounded transition-colors"
                title="Open in new tab"
              >
                <ExternalLink className="h-4 w-4 text-slate-300" />
              </a>
            </div>
          </div>

          {/* PDF Content - Using embed for better compatibility */}
          <div className="flex-1 overflow-auto bg-slate-950">
            {pdfUrl ? (
              <embed
                src={pdfUrl}
                type="application/pdf"
                className="w-full h-full"
                title="Document Preview"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                No PDF URL available
              </div>
            )}
          </div>
        </div>

        {/* Chat Interface */}
        <div className="xl:col-span-7 border border-slate-700 rounded-2xl overflow-hidden flex flex-col bg-slate-900/80 shadow-xl shadow-black/20 min-h-105">
          <div className="bg-slate-950/90 border-b border-slate-700 p-4">
            <h3 className="font-semibold text-slate-100">Ask Questions</h3>
            <p className="text-xs text-slate-400 mt-1">Your legal assistant for clause review, risk spotting, obligations, and negotiation guidance</p>
          </div>

          {/* Messages */}
          <div
            ref={messagesContainerRef}
            className="flex-1 overflow-auto no-scrollbar p-4 space-y-4 bg-linear-to-b from-slate-900/60 to-slate-950/80"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-center">
                <div>
                  <p className="text-slate-400">No messages yet</p>
                  <p className="text-xs text-slate-500 mt-1">Ask a question about the document</p>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-2 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-linear-to-r from-cyan-500 to-blue-600 text-white'
                        : 'bg-slate-800 text-slate-100 border border-slate-700'
                    }`}
                  >
                    <div className="text-sm prose prose-sm prose-invert max-w-none">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-slate-800 text-slate-100 px-4 py-2 rounded-lg border border-slate-700">
                  {streamingText ? (
                    <div className="text-sm prose prose-sm prose-invert max-w-none">
                      <ReactMarkdown>{streamingText}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-cyan-300 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-cyan-300 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-cyan-300 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-slate-700 p-4 bg-slate-950/80">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Ask a question..."
                className="flex-1 px-3 py-2 border border-slate-600 bg-slate-900 text-slate-100! placeholder-slate-400! rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                disabled={isLoading}
              />
              <button
                onClick={handleSendMessage}
                disabled={isLoading || !input.trim()}
                className="px-4 py-2 bg-linear-to-r from-cyan-500 to-blue-600 text-white rounded-lg hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
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
