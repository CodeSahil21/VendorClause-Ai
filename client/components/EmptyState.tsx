interface EmptyStateProps {
  onCreateSession: () => void;
}

export default function EmptyState({ onCreateSession }: EmptyStateProps) {
  return (
    <div className="text-center py-16 bg-slate-950 rounded-2xl shadow-sm border border-slate-700">
      <div className="max-w-md mx-auto px-6">
        <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-linear-to-br from-cyan-500/25 to-blue-500/25 border border-cyan-500/30 flex items-center justify-center">
          <svg className="w-10 h-10 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </div>
        <h3 className="text-xl font-bold text-slate-100 mb-2">No sessions yet</h3>
        <p className="text-slate-400 mb-6">Create your first session to start analyzing vendor agreements with AI-powered insights.</p>
        <button
          onClick={onCreateSession}
          className="inline-flex items-center px-6 py-3 bg-linear-to-r from-cyan-500 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-600 hover:to-blue-700 transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          Create Your First Session
        </button>
      </div>
    </div>
  );
}
