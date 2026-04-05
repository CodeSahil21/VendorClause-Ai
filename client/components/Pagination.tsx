interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <div className="mt-8 flex items-center justify-center space-x-3">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-5 py-2.5 border-2 border-slate-600 bg-slate-900 text-slate-200 font-medium rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-800 hover:border-cyan-500/60 transition-all flex items-center space-x-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
        </svg>
        <span>Previous</span>
      </button>
      
      <div className="px-6 py-2.5 bg-linear-to-r from-cyan-500/15 to-blue-500/15 border-2 border-cyan-500/40 rounded-xl">
        <span className="text-sm font-semibold text-cyan-200">
          Page {currentPage} of {totalPages}
        </span>
      </div>
      
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-5 py-2.5 border-2 border-slate-600 bg-slate-900 text-slate-200 font-medium rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-800 hover:border-cyan-500/60 transition-all flex items-center space-x-2"
      >
        <span>Next</span>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}
