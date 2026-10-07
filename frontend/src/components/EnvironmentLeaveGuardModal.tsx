import { type FC } from 'react';

interface EnvironmentLeaveGuardModalProps {
  isOpen: boolean;
  onStay: () => void;
  onStopAndLeave: () => void;
  isStopping: boolean;
  stopError: string | null;
}

export const EnvironmentLeaveGuardModal: FC<EnvironmentLeaveGuardModalProps> = ({
  isOpen,
  onStay,
  onStopAndLeave,
  isStopping,
  stopError,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={!isStopping ? onStay : undefined}
      />

      {/* Modal Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="leave-guard-title"
        className="relative bg-[var(--surface)] border border-[var(--border)] rounded-lg w-full max-w-md p-6 shadow-2xl animate-fade-in"
      >
        <div className="flex items-center gap-2 mb-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] inline-block animate-pulse-subtle" />
          <h2
            id="leave-guard-title"
            className="font-serif text-lg sm:text-xl text-[var(--text)] font-semibold tracking-wide"
          >
            Environment Still Running
          </h2>
        </div>

        <p className="text-xs sm:text-sm text-[var(--text-muted)] mb-6 leading-relaxed">
          Your CTF environment is still active.
          <br /><br />
          Please stop the environment before leaving to avoid wasting your session time.
        </p>

        {stopError && (
          <div className="mb-4 p-3 bg-[var(--danger-subtle)] border border-[var(--danger)]/30 rounded text-xs text-[var(--danger)] leading-relaxed flex items-start gap-2">
            <svg
              className="w-4 h-4 shrink-0 mt-0.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{stopError}</span>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onStay}
            disabled={isStopping}
            className="btn-outline flex-1 py-2.5 text-xs font-mono uppercase tracking-wider cursor-pointer disabled:opacity-50"
          >
            Stay
          </button>
          <button
            type="button"
            onClick={onStopAndLeave}
            disabled={isStopping}
            className="btn-primary flex-1 py-2.5 text-xs font-mono uppercase tracking-wider bg-[var(--danger)] hover:bg-[var(--danger)]/85 text-white flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {isStopping ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Stopping...
              </>
            ) : (
              'Stop Environment'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
