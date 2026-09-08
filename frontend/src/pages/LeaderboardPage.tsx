import { useState, useEffect } from 'react';

/**
 * LeaderboardPage — Minimal editorial table (reference design language).
 * Simple ranked table of top players.
 */

interface LeaderboardEntry {
  rank: number;
  username: string;
  points: number;
  challenges_solved: number;
}

export function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // The backend doesn't have a leaderboard endpoint yet.
    // Show placeholder data structure — will connect when API exists.
    const timer = setTimeout(() => {
      setEntries([]);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="max-w-2xl">
      <h1 className="font-serif text-3xl text-[var(--text)] mb-1">Leaderboard</h1>
      <p className="text-[var(--text-muted)] text-sm mb-8">Top investigators ranked by performance.</p>

      {loading ? (
        <p className="text-[var(--text-faint)] text-sm animate-pulse-subtle">Loading...</p>
      ) : entries.length === 0 ? (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-8 text-center">
          <p className="text-[var(--text-muted)] text-sm">No rankings yet.</p>
          <p className="text-[var(--text-faint)] text-xs mt-2">Complete challenges to appear on the leaderboard.</p>
        </div>
      ) : (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[3rem_1fr_5rem_5rem] gap-4 px-4 py-2.5 border-b border-[var(--border)] text-[10px] font-mono uppercase tracking-wider text-[var(--text-faint)]">
            <span>#</span>
            <span>Player</span>
            <span className="text-right">Points</span>
            <span className="text-right">Solved</span>
          </div>

          {/* Rows */}
          {entries.map((entry) => (
            <div
              key={entry.rank}
              className="grid grid-cols-[3rem_1fr_5rem_5rem] gap-4 px-4 py-3 border-b border-[var(--border)]/50 last:border-0 hover:bg-[var(--surface-alt)] transition-colors"
            >
              <span className="font-mono text-sm text-[var(--text-faint)]">
                {String(entry.rank).padStart(2, '0')}
              </span>
              <span className="text-sm text-[var(--text)]">{entry.username}</span>
              <span className="text-sm text-[var(--accent)] text-right font-mono">{entry.points}</span>
              <span className="text-sm text-[var(--text-muted)] text-right">{entry.challenges_solved}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
