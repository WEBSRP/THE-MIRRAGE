import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getChallenges, submitFlag, type Challenge, type FlagSubmitResponse } from '../services/challengeService';
import { getSessionStatus, type SessionStatusResponse } from '../services/sessionService';

/**
 * ChallengeDetailPage — Individual challenge view (reference screen 09).
 * Case-file / investigation layout.
 */

function getDifficulty(points: number): { label: string; badge: string } {
  if (points <= 100) return { label: 'Easy', badge: 'badge-easy' };
  if (points <= 250) return { label: 'Medium', badge: 'badge-medium' };
  if (points <= 500) return { label: 'Hard', badge: 'badge-hard' };
  return { label: 'Expert', badge: 'badge-expert' };
}

export function ChallengeDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [session, setSession] = useState<SessionStatusResponse | null>(null);
  const [flag, setFlag] = useState('');
  const [submitResult, setSubmitResult] = useState<FlagSubmitResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const challenges = await getChallenges();
        const found = challenges.find((c) => c.slug === slug);
        if (found) setChallenge(found);
        else setError('Challenge not found.');
      } catch {
        setError('Failed to load challenge.');
      }
      try {
        const status = await getSessionStatus();
        setSession(status);
      } catch {
        // No active session
      }
      setLoading(false);
    }
    load();
  }, [slug]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slug || !flag.trim()) return;
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const result = await submitFlag({ challenge_slug: slug, flag: flag.trim() });
      setSubmitResult(result);
      if (result.is_correct) {
        setChallenge((prev) => prev ? { ...prev, is_solved: true } : prev);
      }
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      setSubmitResult({ is_correct: false, message: apiErr.message || 'Submission failed.', points_awarded: 0, already_solved: false });
    }
    setSubmitting(false);
  }, [slug, flag]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-[var(--text-faint)] text-sm animate-pulse-subtle">Loading...</p>
      </div>
    );
  }

  if (error || !challenge) {
    return (
      <div className="max-w-2xl mx-auto py-16 px-6">
        <p className="text-[var(--danger)] text-sm">{error || 'Challenge not found.'}</p>
        <Link to="/challenges" className="text-[var(--accent)] text-sm mt-4 inline-block hover:underline">
          ← Back to Challenges
        </Link>
      </div>
    );
  }

  const difficulty = getDifficulty(challenge.points);

  return (
    <div className="max-w-2xl mx-auto py-8 px-6">
      {/* Back link */}
      <Link
        to="/challenges"
        className="text-[var(--accent)] text-[12px] hover:underline inline-flex items-center gap-1 mb-8"
      >
        ← Back to Challenges
      </Link>

      {/* Title + badge */}
      <div className="flex items-start gap-3 mb-2">
        <h1 className="font-serif text-3xl text-[var(--text)] leading-tight">{challenge.title}</h1>
        <span className={`${difficulty.badge} text-[10px] px-2.5 py-0.5 rounded-full font-medium uppercase tracking-wider mt-2 shrink-0`}>
          {difficulty.label}
        </span>
      </div>

      {/* Category */}
      <p className="text-[var(--text-muted)] text-sm mb-6">{challenge.category}</p>

      {/* Description */}
      <div className="mb-8">
        <p className="text-[var(--text)] text-sm leading-relaxed">{challenge.description}</p>
      </div>

      {/* Target info card */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-4 mb-6 space-y-2">
        <div className="flex justify-between text-[12px]">
          <span className="text-[var(--text-faint)]">Target</span>
          <span className="font-mono text-[var(--text)]">
            {session?.mirage_ip || '10.42.0.17'}
          </span>
        </div>
        <div className="flex justify-between text-[12px]">
          <span className="text-[var(--text-faint)]">VPN Required</span>
          <span className="text-[var(--text)]">Yes</span>
        </div>
        <div className="flex justify-between text-[12px]">
          <span className="text-[var(--text-faint)]">Estimated Time</span>
          <span className="text-[var(--text)]">30–60 minutes</span>
        </div>
        <div className="flex justify-between text-[12px]">
          <span className="text-[var(--text-faint)]">Points</span>
          <span className="text-[var(--text)]">{challenge.points}</span>
        </div>
      </div>

      {/* Hint */}
      {challenge.hint && (
        <div className="mb-6">
          <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-faint)] mb-1.5">Hint</p>
          <p className="text-[var(--text-muted)] text-[13px] italic leading-relaxed">{challenge.hint}</p>
        </div>
      )}

      {/* Flag submission */}
      {challenge.is_solved ? (
        <div className="bg-[var(--success-subtle)] border border-[var(--success)]/20 rounded p-4">
          <p className="text-[var(--success)] text-sm font-medium">✓ Challenge Solved</p>
          <p className="text-[var(--text-muted)] text-xs mt-1">You've already completed this challenge.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-faint)] mb-1.5 block">
              Submit Flag
            </label>
            <input
              type="text"
              value={flag}
              onChange={(e) => setFlag(e.target.value)}
              placeholder="MIRRAGE{...}"
              className="font-mono text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={submitting || !flag.trim()}
            className="btn-primary w-full"
          >
            {submitting ? 'Submitting...' : 'Start Challenge →'}
          </button>
        </form>
      )}

      {/* Submit result */}
      {submitResult && (
        <div className={`mt-4 rounded p-3 text-sm ${
          submitResult.is_correct
            ? 'bg-[var(--success-subtle)] border border-[var(--success)]/20 text-[var(--success)]'
            : 'bg-[var(--danger-subtle)] border border-[var(--danger)]/20 text-[var(--danger)]'
        }`}>
          {submitResult.message}
          {submitResult.is_correct && submitResult.points_awarded > 0 && (
            <span className="block text-xs mt-1">+{submitResult.points_awarded} points</span>
          )}
        </div>
      )}

      {/* Bottom decorative text */}
      <p className="text-[var(--text-faint)] text-[10px] font-mono tracking-wider mt-12 text-right italic">
        "Some structures are never meant to be opened."
      </p>
    </div>
  );
}
