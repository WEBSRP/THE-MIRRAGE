import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { MirrageLogo } from '../components/MirrageLogo';
import { createSession, getSessionStatus } from '../services/sessionService';

/**
 * SessionPage — Session initialization view (reference screen 06).
 * Shows progress checklist as environment initializes.
 */

interface InitStep {
  label: string;
  status: 'pending' | 'active' | 'done' | 'error';
}

const INIT_STEPS: string[] = [
  'Allocating isolated environment...',
  'Configuring network...',
  'Starting services...',
  'Enabling monitoring...',
  'Almost ready...',
];

export function SessionPage() {
  const navigate = useNavigate();
  const [steps, setSteps] = useState<InitStep[]>(
    INIT_STEPS.map((label) => ({ label, status: 'pending' }))
  );
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);

  const advanceStep = useCallback((index: number) => {
    setSteps((prev) =>
      prev.map((step, i) => {
        if (i < index) return { ...step, status: 'done' };
        if (i === index) return { ...step, status: 'active' };
        return step;
      })
    );
    setProgress(Math.round(((index + 1) / INIT_STEPS.length) * 100));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function initSession() {
      try {
        // Step 1: Create session
        advanceStep(0);
        const session = await createSession();
        if (cancelled) return;
        setSessionId(session.session_id);

        // Step 2: Configuring
        advanceStep(1);
        await new Promise((r) => setTimeout(r, 800));
        if (cancelled) return;

        // Step 3: Starting services
        advanceStep(2);
        await new Promise((r) => setTimeout(r, 600));
        if (cancelled) return;

        // Step 4: Monitoring
        advanceStep(3);

        // Poll for ready
        let attempts = 0;
        while (attempts < 30 && !cancelled) {
          try {
            const status = await getSessionStatus(session.session_id);
            if (status.is_ready) {
              advanceStep(4);
              setSteps((prev) => prev.map((s) => ({ ...s, status: 'done' })));
              setProgress(100);
              await new Promise((r) => setTimeout(r, 500));
              if (!cancelled) navigate('/dashboard');
              return;
            }
          } catch {
            // Keep polling
          }
          await new Promise((r) => setTimeout(r, 2000));
          attempts++;
        }

        // If we get here, session is ready enough — proceed
        advanceStep(4);
        setSteps((prev) => prev.map((s) => ({ ...s, status: 'done' })));
        setProgress(100);
        await new Promise((r) => setTimeout(r, 500));
        if (!cancelled) navigate('/dashboard');
      } catch (err: unknown) {
        if (cancelled) return;
        const apiErr = err as { message?: string };
        setError(apiErr.message || 'Failed to initialize environment.');
        setSteps((prev) =>
          prev.map((step) =>
            step.status === 'active' ? { ...step, status: 'error' } : step
          )
        );
      }
    }

    initSession();
    return () => { cancelled = true; };
  }, [navigate, advanceStep]);

  return (
    <div className="min-h-screen bg-[var(--bg)] flex">
      {/* Left content */}
      <div className="flex-1 flex flex-col justify-center px-12 max-w-xl mx-auto">
        <MirrageLogo size="lg" className="mb-12" />

        <h1 className="font-mono text-sm uppercase tracking-[0.15em] text-[var(--text)] mb-8">
          Initializing Environment
        </h1>

        {/* Progress bar */}
        <div className="mb-8">
          <div className="h-1 bg-[var(--surface-alt)] rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--accent)] rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="font-mono text-[11px] text-[var(--text-faint)] mt-2 text-right">
            {progress}%
          </p>
        </div>

        {/* Steps checklist */}
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div key={i} className="flex items-center gap-3">
              {/* Status icon */}
              <div className="w-4 h-4 flex items-center justify-center shrink-0">
                {step.status === 'done' && (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M3 7l3 3 5-5" stroke="var(--success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                {step.status === 'active' && (
                  <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse-subtle" />
                )}
                {step.status === 'error' && (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <circle cx="7" cy="7" r="5" stroke="var(--danger)" strokeWidth="1.2" />
                    <path d="M7 5v3M7 9.5v.5" stroke="var(--danger)" strokeWidth="1.2" strokeLinecap="round" />
                  </svg>
                )}
                {step.status === 'pending' && (
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--text-faint)]" />
                )}
              </div>
              <span className={`text-sm ${
                step.status === 'done' ? 'text-[var(--text)]' :
                step.status === 'active' ? 'text-[var(--text)]' :
                step.status === 'error' ? 'text-[var(--danger)]' :
                'text-[var(--text-faint)]'
              }`}>
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {error && (
          <div className="mt-6 bg-[var(--danger-subtle)] border border-[var(--danger)]/20 rounded p-3">
            <p className="text-[var(--danger)] text-sm">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="text-[var(--accent)] text-xs mt-2 hover:underline cursor-pointer"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      {/* Right decorative */}
      <div className="hidden lg:flex flex-col justify-end items-end p-12 w-64">
        <p className="font-mono text-[11px] text-right text-[var(--text-faint)] leading-relaxed tracking-wider mb-4">
          {sessionId && (
            <span className="block text-[var(--text-muted)] mb-2 text-[10px]">
              SESSION<br />
              Initializing...
            </span>
          )}
        </p>
        <p className="font-serif text-sm text-[var(--text-faint)] italic text-right leading-relaxed">
          "What you see<br />is not what was built."
        </p>
      </div>
    </div>
  );
}
