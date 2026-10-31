import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getChallenges, type Challenge } from '../services/challengeService';

type Difficulty = 'Easy' | 'Medium' | 'Hard' | 'Expert';
type Filter = 'All' | Difficulty;

const getDifficulty = (points: number): Difficulty => {
  if (points <= 100) return 'Easy';
  if (points <= 250) return 'Medium';
  if (points <= 500) return 'Hard';
  return 'Expert';
};

const badgeClasses: Record<Difficulty, string> = {
  Easy: 'badge-easy',
  Medium: 'badge-medium',
  Hard: 'badge-hard',
  Expert: 'badge-expert'
};

export function ChallengesPage() {
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('All');

  useEffect(() => {
    let mounted = true;
    const fetchChallenges = async () => {
      try {
        const data = await getChallenges();
        if (mounted) {
          setChallenges(data);
          setError(null);
        }
      } catch {
        if (mounted) {
          setError('Failed to load challenges.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    fetchChallenges();
    return () => { mounted = false; };
  }, []);

  const filteredChallenges = challenges.filter(c => {
    if (filter === 'All') return true;
    return getDifficulty(c.points) === filter;
  });

  return (
    <div className="relative min-h-full flex flex-col p-6 max-w-4xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="font-serif text-3xl mb-1 text-[var(--text)]">Challenges</h1>
        <p className="text-[var(--text-muted)] text-sm font-sans">
          Real infrastructure. Real scenarios.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {(['All', 'Easy', 'Medium', 'Hard', 'Expert'] as Filter[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              filter === f
                ? 'bg-[var(--accent)] text-[var(--bg)] font-medium'
                : 'border border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--accent)]'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="flex flex-col flex-1">
        {loading && <div className="text-[var(--text-muted)] font-mono text-sm">Loading challenges...</div>}
        {error && <div className="text-red-500 font-mono text-sm">{error}</div>}
        
        {!loading && !error && filteredChallenges.length === 0 && (
          <div className="text-[var(--text-muted)] font-mono text-sm">No challenges found.</div>
        )}

        {!loading && !error && filteredChallenges.map(challenge => {
          const diff = getDifficulty(challenge.points);
          return (
            <Link
              key={challenge.id}
              to={`/challenges/${challenge.slug}`}
              className="group flex flex-col sm:flex-row sm:items-center justify-between bg-[var(--surface)] border border-[var(--border)] rounded p-4 mb-2 hover:border-[var(--accent)] transition-colors"
            >
              <div className="flex items-center gap-3 mb-2 sm:mb-0">
                {challenge.is_solved && (
                  <span className="text-[var(--accent)] text-sm font-bold">✓</span>
                )}
                <div>
                  <div className="text-sm font-medium text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
                    {challenge.title}
                  </div>
                  <div className="text-xs text-[var(--text-muted)] mt-0.5 capitalize">
                    {challenge.category.replace(/-/g, ' ')}
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-4 self-end sm:self-auto">
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wider ${badgeClasses[diff]}`}>
                  {diff}
                </span>
                <span className="text-[var(--text-muted)] group-hover:text-[var(--accent)] transition-colors font-mono">
                  →
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="fixed bottom-6 left-6 [writing-mode:vertical-rl] rotate-180 hidden sm:block">
        <span className="font-mono text-[9px] text-[var(--text-faint)] tracking-[0.15em] uppercase">
          OBSERVATION ENHANCES UNDERSTANDING.
        </span>
      </div>
    </div>
  );
}
