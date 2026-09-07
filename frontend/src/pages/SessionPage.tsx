import { useLocation, Navigate, Link } from 'react-router-dom';
import { useState } from 'react';
import type { SessionResponse } from '../services/sessionService';

/**
 * Session page - displays the Mirage target IP after successful initialization.
 * Only shows the Mirage endpoint. The CTF environment must be discovered through investigation.
 */
export function SessionPage() {
  const location = useLocation();
  const sessionData = location.state as SessionResponse | null;
  const [copied, setCopied] = useState(false);

  // Redirect if no session data
  if (!sessionData) {
    return <Navigate to="/enter" replace />;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sessionData.mirage_ip);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API might not be available
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center px-6 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-[var(--obsidian)] via-[var(--dark-earth)]/30 to-[var(--obsidian)]" />

      <div className="relative z-10 w-full max-w-lg mx-auto text-center">
        <div className="animate-fade-in" style={{ animationDuration: '2s' }}>
          {/* Header */}
          <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-2 uppercase">
            Session Active
          </p>
          <h1 className="font-display text-2xl sm:text-3xl tracking-wide text-[var(--sandstone-light)] mb-12">
            MIRAGE ACCESS
          </h1>

          {/* Target display */}
          <div className="border border-[var(--gold-muted)]/20 bg-[var(--dark-earth)]/40 p-8 sm:p-10 mb-8">
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/70 mb-4 uppercase font-medium">
              Target
            </p>
            <button
              onClick={handleCopy}
              className="group cursor-pointer w-full"
              title="Click to copy"
            >
              <p className="font-mono text-2xl sm:text-3xl text-[var(--gold-muted)] tracking-wider group-hover:text-[var(--sandstone-light)] transition-colors duration-500">
                {sessionData.mirage_ip}
              </p>
              <p className="text-xs text-[var(--sandstone)]/50 mt-3 tracking-wider">
                {copied ? 'Copied to clipboard' : 'Click to copy'}
              </p>
            </button>
          </div>

          {/* Session info */}
          <div className="flex justify-between text-xs text-[var(--sandstone)]/60 tracking-wider mb-12 px-2">
            <span>ID: {sessionData.session_id}</span>
            <span>STATUS: {sessionData.status.toUpperCase()}</span>
          </div>

          {/* Investigation prompt */}
          <div className="border-t border-[var(--gold-muted)]/15 pt-8 max-w-sm mx-auto">
            <p className="text-sm text-[var(--sandstone)]/75 leading-relaxed mb-2">
              You have been granted access to the archive.
            </p>
            <p className="text-sm text-[var(--sandstone)]/70 leading-relaxed">
              Begin your investigation. Not everything is where you expect it to be.
            </p>
          </div>

          {/* Hidden hint */}
          <p className="mt-16 text-xs text-[var(--sandstone)]/20 tracking-[0.2em]">
            The second layer awaits those who look carefully.
          </p>

          {/* Return link */}
          <div className="mt-8">
            <Link
              to="/"
              className="text-xs text-[var(--sandstone)]/50 tracking-wider hover:text-[var(--sandstone)]/70 transition-colors duration-500"
            >
              RETURN TO SURFACE
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
