import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCountdown } from '../hooks/useCountdown';
import { createSession, type SessionResponse } from '../services/sessionService';

type Phase = 'idle' | 'initializing' | 'ready' | 'error';

/** Initialization messages displayed during the countdown */
const INIT_MESSAGES = [
  { time: 90, text: 'Preparing your passage...' },
  { time: 75, text: 'Establishing access...' },
  { time: 55, text: 'Verifying the archive...' },
  { time: 35, text: 'Aligning the coordinates...' },
  { time: 15, text: 'Opening the passage...' },
  { time: 5, text: 'Access granted.' },
];

export function EnterPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>('idle');
  const [currentMessage, setCurrentMessage] = useState('');
  const [sessionData, setSessionData] = useState<SessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCountdownComplete = useCallback(async () => {
    try {
      const data = await createSession();
      setSessionData(data);
      setPhase('ready');
    } catch {
      setError('The passage could not be opened. Please try again.');
      setPhase('error');
    }
  }, []);

  const { minutes, seconds, progress, start, isRunning, isComplete } = useCountdown({
    totalSeconds: 90,
    onComplete: handleCountdownComplete,
  });

  // Update initialization message based on time remaining
  const timeLeft = 90 - Math.floor(progress * 90);
  useEffect(() => {
    if (!isRunning && !isComplete) return;
    const msg = INIT_MESSAGES.find((m) => timeLeft <= m.time);
    if (msg) {
      setCurrentMessage(msg.text);
    }
  }, [timeLeft, isRunning, isComplete]);

  const handleEnter = () => {
    setPhase('initializing');
    start();
  };

  // Navigate to session page when ready
  useEffect(() => {
    if (phase === 'ready' && sessionData) {
      const timer = setTimeout(() => {
        navigate('/session', { state: sessionData });
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [phase, sessionData, navigate]);

  return (
    <main className="min-h-screen flex items-center justify-center px-6 relative overflow-hidden">
      {/* Atmospheric background */}
      <div className="absolute inset-0 bg-gradient-to-b from-[var(--obsidian)] via-[var(--dark-earth)]/40 to-[var(--obsidian)]" />

      {/* Subtle pyramid silhouette */}
      <svg
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-5xl opacity-[0.03]"
        viewBox="0 0 1000 500"
        aria-hidden="true"
      >
        <polygon
          points="500,50 100,450 900,450"
          fill="currentColor"
          className="text-[var(--sandstone)]"
        />
      </svg>

      <div className="relative z-10 w-full max-w-lg mx-auto text-center">
        {/* ─── IDLE STATE ─── */}
        {phase === 'idle' && (
          <div className="animate-fade-in" style={{ animationDuration: '1.5s' }}>
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-8 uppercase">
              Passage
            </p>
            <h1 className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-wide text-[var(--sandstone-light)] mb-6">
              ENTER THE MIRAGE
            </h1>
            <p className="text-sm text-[var(--sandstone)]/70 mb-12 max-w-sm mx-auto leading-relaxed">
              You are about to be granted access to something you were not necessarily meant to
              find.
            </p>

            <button
              onClick={handleEnter}
              className="inline-block border border-[var(--gold-muted)]/40 px-10 py-4 text-sm font-medium tracking-wider text-[var(--gold-muted)] hover:bg-[var(--gold-muted)]/10 hover:border-[var(--gold-muted)]/60 transition-all duration-700 cursor-pointer"
            >
              INITIATE PASSAGE
            </button>

            <p className="mt-12 text-xs text-[var(--sandstone)]/40 tracking-wider italic">
              Trust what you find. Question where you found it.
            </p>
          </div>
        )}

        {/* ─── INITIALIZING STATE ─── */}
        {phase === 'initializing' && (
          <div className="animate-fade-in" style={{ animationDuration: '1s' }}>
            {/* Countdown timer */}
            <div className="mb-12">
              <p className="font-display text-6xl sm:text-7xl tracking-wider text-[var(--sandstone-light)] tabular-nums">
                {minutes}:{seconds}
              </p>
            </div>

            {/* Progress bar */}
            <div className="w-full max-w-xs mx-auto mb-12">
              <div className="h-px bg-[var(--gold-muted)]/10 relative overflow-hidden">
                <div
                  className="h-full bg-[var(--gold-muted)]/40 transition-all duration-1000 ease-linear"
                  style={{ width: `${progress * 100}%` }}
                />
              </div>
            </div>

            {/* Status message */}
            <p
              className="text-base text-[var(--sandstone)]/75 tracking-wide min-h-[2em] transition-opacity duration-700"
              key={currentMessage}
            >
              {currentMessage}
            </p>

            {/* Decorative rotating symbol */}
            <div className="mt-16 text-[var(--sandstone)]/10 text-3xl animate-spin" style={{ animationDuration: '20s' }}>
              𓋹
            </div>
          </div>
        )}

        {/* ─── READY STATE ─── */}
        {phase === 'ready' && sessionData && (
          <div className="animate-fade-in" style={{ animationDuration: '1.5s' }}>
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-6 uppercase">
              Access Granted
            </p>
            <h2 className="font-display text-2xl tracking-wide text-[var(--sandstone-light)] mb-4">
              PASSAGE OPENED
            </h2>
            <p className="text-sm text-[var(--sandstone)]/70 tracking-wider">
              Redirecting...
            </p>
          </div>
        )}

        {/* ─── ERROR STATE ─── */}
        {phase === 'error' && (
          <div className="animate-fade-in" style={{ animationDuration: '1s' }}>
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-6 uppercase">
              Obstruction
            </p>
            <p className="text-sm text-[var(--sandstone)]/70 mb-8">{error}</p>
            <button
              onClick={() => {
                setPhase('idle');
                setError(null);
              }}
              className="inline-block border border-[var(--gold-muted)]/30 px-8 py-3 text-sm font-medium tracking-wider text-[var(--gold-muted)]/70 hover:bg-[var(--gold-muted)]/10 transition-all duration-500 cursor-pointer"
            >
              TRY AGAIN
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
