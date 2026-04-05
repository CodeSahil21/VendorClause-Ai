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
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-cyan-300/30 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 top-24 h-80 w-80 rounded-full bg-blue-300/35 blur-3xl" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        {/* Header */}
        <section className="mb-8 rounded-3xl border border-cyan-100/80 bg-slate-950/90 p-5 sm:p-7 shadow-xl shadow-slate-900/20 backdrop-blur-sm">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="inline-flex items-center rounded-full border border-cyan-400/40 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-300">
                Workspace Overview
              </div>
              <h2 className="mt-3 text-3xl sm:text-4xl font-black tracking-tight text-slate-100">Your Sessions</h2>
              <p className="mt-2 text-slate-300 flex items-center">
                <svg className="w-5 h-5 mr-2 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Manage your document analysis sessions in one place
              </p>
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-linear-to-r from-cyan-500 to-blue-600 px-6 py-3 font-semibold text-white transition-all duration-300 hover:-translate-y-0.5 hover:from-cyan-600 hover:to-blue-700 hover:shadow-lg hover:shadow-cyan-500/20 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-950"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              <span>New Session</span>
            </button>
          </div>

        </section>

        {/* Content */}
        {sessions.length === 0 ? (
          <EmptyState onCreateSession={() => setShowModal(true)} />
        ) : (
          <>
            <section className="rounded-3xl border border-cyan-100/80 bg-slate-900/65 p-4 sm:p-6 shadow-lg shadow-slate-900/15 backdrop-blur-sm">
              <div className="mb-5 flex items-center justify-between">
                <h3 className="text-lg sm:text-xl font-bold text-slate-100">Recent Sessions</h3>
                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs sm:text-sm font-medium text-slate-300 border border-slate-700">
                  {sessions.length} visible
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {sessions.map((session, index) => (
                  <div
                    key={session.id}
                    className="animate-fadeIn"
                    style={{ animationDelay: `${index * 70}ms`, animationFillMode: 'both' }}
                  >
                    <SessionCard
                      session={session}
                      onDelete={handleDeleteClick}
                      onClick={handleSessionClick}
                    />
                  </div>
                ))}
              </div>
            </section>

            {pagination && (
              <Pagination
                currentPage={pagination.page}
                totalPages={pagination.totalPages}
                onPageChange={getUserSessions}
              />
            )}
          </>
        )}

      </div>

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
