'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { useSessionStore } from '@/store';
import CreateSessionModal from '@/components/CreateSessionModal';
import SessionCard from '@/components/SessionCard';
import EmptyState from '@/components/EmptyState';
import Pagination from '@/components/Pagination';
import SessionsSkeleton from '@/components/SessionsSkeleton';
import ConfirmDialog from '@/components/ConfirmDialog';

export default function Home() {
  const router = useRouter();
  const { sessions, pagination, isLoading, getUserSessions, createSession, deleteSession } = useSessionStore();
  const [showModal, setShowModal] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{ isOpen: boolean; sessionId: string | null }>({ isOpen: false, sessionId: null });
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    getUserSessions();
  }, [getUserSessions]);

  const handleSessionClick = (sessionId: string) => {
    router.push(`/home/session/${sessionId}`);
  };

  const handleDeleteClick = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteDialog({ isOpen: true, sessionId });
  };

  const handleConfirmDelete = async () => {
    if (!deleteDialog.sessionId) return;

    setIsDeleting(true);
    try {
      await deleteSession(deleteDialog.sessionId);
      toast.success('Session deleted successfully');
      setDeleteDialog({ isOpen: false, sessionId: null });
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return <SessionsSkeleton />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8 space-y-4 sm:space-y-0">
        <div>
          <h2 className="text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">Your Sessions</h2>
          <p className="mt-2 text-gray-600 flex items-center">
            <svg className="w-5 h-5 mr-2 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Manage your document analysis sessions
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all shadow-lg hover:shadow-xl flex items-center space-x-2 transform hover:-translate-y-0.5"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          <span>New Session</span>
        </button>
      </div>

      {/* Stats Bar */}
      {sessions.length > 0 && (
        <div className="mb-8 p-4 bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 rounded-xl border border-indigo-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Sessions</p>
                <p className="text-2xl font-bold text-gray-900">{pagination?.total || sessions.length}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Active Now</p>
              <p className="text-lg font-semibold text-indigo-600">{sessions.length} sessions</p>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      {sessions.length === 0 ? (
        <EmptyState onCreateSession={() => setShowModal(true)} />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sessions.map((session) => (
              <SessionCard
                key={session.id}
                session={session}
                onDelete={handleDeleteClick}
                onClick={handleSessionClick}
              />
            ))}
          </div>
          {pagination && (
            <Pagination
              currentPage={pagination.page}
              totalPages={pagination.totalPages}
              onPageChange={getUserSessions}
            />
          )}
        </>
      )}

      {/* Create Session Modal */}
      <CreateSessionModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={() => setShowModal(false)}
        createSession={createSession}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteDialog.isOpen}
        title="Delete Session"
        message="Are you sure you want to delete this session? This action cannot be undone."
        confirmText="Delete"
        cancelText="Cancel"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteDialog({ isOpen: false, sessionId: null })}
        isLoading={isDeleting}
      />
    </div>
  );
}
