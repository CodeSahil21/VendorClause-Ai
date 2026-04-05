export default function SessionsSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-pulse">
      {/* Header Skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8 space-y-4 sm:space-y-0">
        <div>
          <div className="h-10 w-64 bg-linear-to-r from-slate-300 to-slate-400 rounded-lg mb-2"></div>
          <div className="h-5 w-80 bg-slate-300 rounded-lg"></div>
        </div>
        <div className="h-12 w-40 bg-linear-to-r from-cyan-200 to-blue-300 rounded-xl"></div>
      </div>

      {/* Stats Bar Skeleton */}
      <div className="mb-8 p-4 bg-linear-to-r from-slate-200 to-cyan-100 rounded-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-10 h-10 bg-slate-400 rounded-lg"></div>
            <div>
              <div className="h-4 w-24 bg-slate-400 rounded mb-2"></div>
              <div className="h-8 w-16 bg-slate-400 rounded"></div>
            </div>
          </div>
          <div className="text-right">
            <div className="h-4 w-20 bg-slate-400 rounded mb-2"></div>
            <div className="h-6 w-24 bg-slate-400 rounded"></div>
          </div>
        </div>
      </div>

      {/* Cards Grid Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-slate-800 rounded-2xl shadow-md border border-slate-700 p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-2">
                  <div className="w-8 h-8 bg-linear-to-br from-cyan-300 to-blue-400 rounded-lg"></div>
                  <div className="h-6 w-40 bg-slate-500 rounded"></div>
                </div>
                <div className="h-4 w-32 bg-slate-500 rounded"></div>
              </div>
              <div className="w-9 h-9 bg-slate-500 rounded-lg"></div>
            </div>
            <div className="pt-4 border-t border-slate-700">
              <div className="h-4 w-48 bg-slate-500 rounded"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
