'use client';

import { useRouter } from 'next/navigation';
import Image from 'next/image';
import toast from 'react-hot-toast';
import { useAuthStore } from '@/store';
import { SocketProvider } from '@/context/SocketContext';

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, logout, isLoading } = useAuthStore();

  const handleLogout = async () => {
    try {
      await logout();
      toast.success('Logged out successfully');
      router.push('/login');
    } catch {
      toast.error('Logout failed');
    }
  };

  const getInitials = (name?: string | null) => {
    if (!name) return user?.email?.charAt(0).toUpperCase() || 'U';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <SocketProvider>
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-indigo-50">
      {/* Navbar */}
      <nav className="bg-white/80 backdrop-blur-lg shadow-sm border-b border-gray-200/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Left - Logo */}
            <div className="flex items-center space-x-3 group cursor-pointer">
              <div className="relative">
                <Image src="/App.png" alt="VendorClause AI" width={40} height={40} className="rounded-full ring-2 ring-indigo-100 group-hover:ring-indigo-300 transition-all" />
                <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-white animate-pulse"></div>
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">VendorClause AI</h1>
                <p className="text-xs text-gray-500">Contract Intelligence</p>
              </div>
            </div>

            {/* Right - User Info & Logout */}
            <div className="flex items-center space-x-4">
              {/* User Avatar */}
              <div className="flex items-center space-x-3 px-4 py-2 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border border-indigo-100 hover:border-indigo-200 transition-all">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm shadow-md">
                  {getInitials(user?.name)}
                </div>
                <div className="hidden sm:block">
                  <p className="text-sm font-semibold text-gray-900">{user?.name || 'User'}</p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                </div>
              </div>

              {/* Logout Button */}
              <button
                onClick={handleLogout}
                disabled={isLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-red-600 rounded-xl hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 transition-all shadow-md hover:shadow-lg transform hover:-translate-y-0.5 flex items-center space-x-2"
              >
                {isLoading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span className="hidden sm:inline">Logging out...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    <span className="hidden sm:inline">Logout</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main>{children}</main>
      </div>
    </SocketProvider>
  );
}
