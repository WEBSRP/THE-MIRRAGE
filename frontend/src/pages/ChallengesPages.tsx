import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Badge, Button, Card, EmptyState, ProgressBar, SelectField, StatusBadge, TextField } from '../components/ui';
import { difficultyOptions, type Difficulty } from '../data/mockData';
import { useApp, type ExtendedChallenge } from '../state/AppState';

export function ChallengesPage() {
  const { challenges, solvedChallengeIds } = useApp();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [difficulty, setDifficulty] = useState('all');
  const [status, setStatus] = useState('all');
  const [sort, setSort] = useState('recommended');

  const categories = useMemo(() => {
    const list = Array.from(new Set(challenges.map((c) => c.category))).filter(Boolean);
    return list.length ? list : ['Perception', 'Deception', 'Forensics', 'Web', 'Network'];
  }, [challenges]);

  const visible = useMemo(() => {
    const filtered = challenges.filter((challenge) => {
      const query = search.toLowerCase();
      const matchesSearch =
        !query ||
        `${challenge.title} ${challenge.description} ${challenge.tags.join(' ')}`.toLowerCase().includes(query);
      const matchesCategory = category === 'all' || challenge.category.toLowerCase() === category.toLowerCase();
      const matchesDifficulty = difficulty === 'all' || challenge.difficulty === difficulty;
      const isSolved = solvedChallengeIds.includes(challenge.slug) || solvedChallengeIds.includes(challenge.id);
      const matchesStatus = status === 'all' || (status === 'solved' ? isSolved : !isSolved);
      return matchesSearch && matchesCategory && matchesDifficulty && matchesStatus;
    });

    return [...filtered].sort((a, b) =>
      sort === 'points'
        ? b.points - a.points
        : sort === 'difficulty'
        ? difficultyOptions.indexOf(b.difficulty) - difficultyOptions.indexOf(a.difficulty)
        : sort === 'time'
        ? parseInt(a.estimatedTime, 10) - parseInt(b.estimatedTime, 10)
        : a.title.localeCompare(b.title)
    );
  }, [category, difficulty, search, sort, solvedChallengeIds, status, challenges]);

  return (
    <div className="platform-page challenges-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">02 / target catalog</span>
          <h1>Challenges</h1>
          <p>Real infrastructure. Dual-container pods with active honeypot deception and hidden CTF targets.</p>
        </div>
        <div className="challenge-header-stat">
          <strong>{solvedChallengeIds.length.toString().padStart(2, '0')}</strong>
          <span>solved<br />targets</span>
        </div>
      </div>

      <Card className="challenge-controls">
        <div className="challenge-search">
          <TextField
            aria-label="Search challenges"
            icon="search"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title, category, or tag"
            type="search"
            value={search}
          />
        </div>
        <div className="challenge-filter-controls">
          <SelectField
            aria-label="Filter by category"
            onChange={(event) => setCategory(event.target.value)}
            options={[
              { value: 'all', label: 'All categories' },
              ...categories.map((opt) => ({ value: opt, label: opt })),
            ]}
            value={category}
          />
          <SelectField
            aria-label="Filter by difficulty"
            onChange={(event) => setDifficulty(event.target.value)}
            options={[
              { value: 'all', label: 'All difficulty' },
              ...difficultyOptions.map((opt) => ({ value: opt, label: opt })),
            ]}
            value={difficulty}
          />
          <SelectField
            aria-label="Filter by status"
            onChange={(event) => setStatus(event.target.value)}
            options={[
              { value: 'all', label: 'All status' },
              { value: 'available', label: 'Available' },
              { value: 'solved', label: 'Solved' },
            ]}
            value={status}
          />
          <SelectField
            aria-label="Sort challenges"
            onChange={(event) => setSort(event.target.value)}
            options={[
              { value: 'recommended', label: 'Sort: Title' },
              { value: 'points', label: 'Sort: Points' },
              { value: 'difficulty', label: 'Sort: Difficulty' },
            ]}
            value={sort}
          />
        </div>
      </Card>

      <div className="challenge-results-bar">
        <span>Showing <strong>{visible.length}</strong> of {challenges.length} active targets</span>
        <span className="challenge-results-note">
          <span className="live-dot" style={{ backgroundColor: 'var(--lime)' }} /> Live cluster verification
        </span>
      </div>

      {visible.length ? (
        <div className="challenge-catalog">
          {visible.map((challenge, index) => {
            const isSolved =
              solvedChallengeIds.includes(challenge.slug) ||
              solvedChallengeIds.includes(challenge.id) ||
              Boolean(challenge.is_solved);
            return (
              <ChallengeRow
                challenge={challenge}
                index={index}
                key={challenge.slug || challenge.id}
                solved={isSolved}
              />
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState
            action={
              <Button
                onClick={() => {
                  setSearch('');
                  setCategory('all');
                  setDifficulty('all');
                  setStatus('all');
                }}
                size="small"
                variant="secondary"
              >
                Reset filters
              </Button>
            }
            icon="search"
            message="Try loosening a filter or searching for another term."
            title="No targets matched"
          />
        </Card>
      )}

      <div className="challenge-catalog-foot">
        <span><span className="live-dot" /> Connected to cluster 10.42.0.0/16 subnet.</span>
        <Link className="inline-link" to="/sessions">
          Inspect active sessions <Icon name="arrow-right" size={14} />
        </Link>
      </div>
    </div>
  );
}

function ChallengeRow({
  challenge,
  index,
  solved,
}: {
  challenge: ExtendedChallenge;
  index: number;
  solved: boolean;
}) {
  const categoryIcon =
    challenge.category.toLowerCase().includes('perception')
      ? 'eye'
      : challenge.category.toLowerCase().includes('deception')
      ? 'shield'
      : challenge.category.toLowerCase().includes('forensic')
      ? 'activity'
      : challenge.category.toLowerCase().includes('web')
      ? 'code'
      : challenge.category.toLowerCase().includes('network')
      ? 'network'
      : 'key';

  return (
    <Link className="challenge-catalog-row" to={`/challenges/${challenge.slug || challenge.id}`}>
      <span className="challenge-catalog-number">{String(index + 1).padStart(2, '0')}</span>
      <span className={`challenge-catalog-icon challenge-icon-${challenge.category.toLowerCase()}`}>
        <Icon name={categoryIcon as any} size={18} />
      </span>
      <span className="challenge-catalog-name">
        <strong>{challenge.title}</strong>
        <small>{challenge.category} · {challenge.tags.join(' · ')}</small>
      </span>
      <span className="challenge-catalog-description">{challenge.description}</span>
      <span className="challenge-catalog-difficulty">
        <Badge tone={difficultyTone(challenge.difficulty)}>{challenge.difficulty}</Badge>
        <small>{challenge.estimatedTime}</small>
      </span>
      <span className="challenge-catalog-points">
        {challenge.points}<small> pts</small>
      </span>
      <span className="challenge-catalog-status">
        {solved ? <StatusBadge status="Solved" /> : <Icon name="arrow-up-right" size={17} />}
      </span>
    </Link>
  );
}

export function ChallengeDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { challenges, solvedChallengeIds, submitFlag, startSession, activeSessionData } = useApp();
  const challenge = challenges.find((item) => item.id === id || item.slug === id || item.backendId === id);

  const [revealedHints, setRevealedHints] = useState<number[]>([]);
  const [flag, setFlag] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error' | 'info'; message: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [starting, setStarting] = useState(false);

  if (!challenge) {
    return (
      <div className="platform-page">
        <EmptyState
          action={<Button onClick={() => navigate('/challenges')} variant="secondary">Back to challenges</Button>}
          icon="search"
          message="That challenge was not found in the current range."
          title="Target not found"
        />
      </div>
    );
  }

  const solved =
    solvedChallengeIds.includes(challenge.slug) ||
    solvedChallengeIds.includes(challenge.id) ||
    Boolean(challenge.is_solved);

  const toggleHint = (index: number) =>
    setRevealedHints((current) =>
      current.includes(index) ? current.filter((item) => item !== index) : [...current, index]
    );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!flag.trim()) return;
    setFeedback(null);
    setSubmitting(true);
    const result = await submitFlag(challenge.slug || challenge.id, flag);
    setSubmitting(false);
    setFeedback({
      tone: result.ok ? 'success' : 'error',
      message: result.message ?? (result.ok ? 'Flag accepted.' : 'Incorrect flag.'),
    });
    if (result.ok) setFlag('');
  };

  const handleStart = async () => {
    setStarting(true);
    const result = await startSession(challenge.slug || challenge.id);
    setStarting(false);
    setFeedback({
      tone: result.ok ? 'info' : 'error',
      message: result.ok ? 'Pod provisioning started. Open Sessions console to access endpoints.' : result.message ?? 'Unable to start session.',
    });
  };

  const currentMirageIp = activeSessionData?.mirage_ip || null;

  return (
    <div className="platform-page challenge-detail-page">
      <div className="detail-breadcrumb">
        <Link to="/challenges">
          <Icon name="arrow-left" size={14} /> Challenges
        </Link>
        <Icon name="chevron-right" size={13} />
        <span>{challenge.title}</span>
      </div>

      <div className="challenge-detail-header">
        <div>
          <div className="challenge-detail-tags">
            <Badge tone={difficultyTone(challenge.difficulty)}>{challenge.difficulty}</Badge>
            <Badge tone="muted">{challenge.category}</Badge>
            <span>{challenge.estimatedTime} estimated</span>
          </div>
          <h1>{challenge.title}</h1>
          <p>{challenge.description}</p>
        </div>
        <div className="challenge-detail-score">
          <strong>{challenge.points}</strong>
          <span>points<br />available</span>
        </div>
      </div>

      <div className="detail-layout">
        <div className="detail-main">
          <Card className="detail-objectives">
            <div className="platform-card-heading">
              <div>
                <span className="platform-card-kicker">Mission brief</span>
                <h2>Observe the system.</h2>
              </div>
              <Badge dot tone={solved ? 'lime' : 'orange'}>
                {solved ? 'Solved' : 'Open target'}
              </Badge>
            </div>
            <p className="detail-lede">
              {challenge.description} Connect to the private subnet via OpenVPN and investigate the target host.
            </p>
            <div className="objective-list">
              {challenge.objectives.map((objective, index) => (
                <div key={objective}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <p>{objective}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="detail-hints">
            <div className="platform-card-heading">
              <div>
                <span className="platform-card-kicker">Investigative guidance</span>
                <h2>Hints & signals.</h2>
              </div>
              <Badge tone="muted">{revealedHints.length}/{challenge.hints.length} revealed</Badge>
            </div>
            <div className="hint-list">
              {challenge.hints.map((hint, index) => (
                <button
                  className={`hint-row ${revealedHints.includes(index) ? 'is-revealed' : ''}`}
                  key={hint}
                  onClick={() => toggleHint(index)}
                  type="button"
                >
                  <span className="hint-number">0{index + 1}</span>
                  <span>{revealedHints.includes(index) ? hint : 'Reveal directional guidance'}</span>
                  <Icon name={revealedHints.includes(index) ? 'eye' : 'eye-off'} size={15} />
                </button>
              ))}
            </div>
          </Card>

          <Card className="detail-terminal-note">
            <span className="detail-terminal-icon">
              <Icon name="server" size={19} />
            </span>
            <div>
              <span className="platform-card-kicker">Environment Pod</span>
              <h3>Dual-Container Cluster Machine</h3>
              <p>
                {currentMirageIp
                  ? `Active target at ${currentMirageIp} (Port 80/22). Accessible via OpenVPN tunnel.`
                  : 'Requires an active environment. Launch a pod to generate isolated honeypot and CTF endpoints.'}
              </p>
            </div>
            <Button
              icon="play"
              loading={starting}
              onClick={handleStart}
              variant="secondary"
            >
              {currentMirageIp ? 'Console' : 'Start pod'}
            </Button>
          </Card>
        </div>

        <aside className="detail-aside">
          <Card className="flag-card">
            <div className="platform-card-heading">
              <div>
                <span className="platform-card-kicker">Flag submission</span>
                <h2>{solved ? 'Signal confirmed.' : 'Submit flag'}</h2>
              </div>
              <Icon name={solved ? 'check' : 'key'} size={19} />
            </div>

            {solved ? (
              <div className="solved-state">
                <span className="solved-check">
                  <Icon name="check" size={20} />
                </span>
                <p>This challenge has been solved. Breakthrough recorded in cluster audit logs.</p>
                <Link className="inline-link" to="/challenges">
                  Next challenge <Icon name="arrow-right" size={14} />
                </Link>
              </div>
            ) : (
              <form className="flag-form" onSubmit={handleSubmit}>
                <TextField
                  autoComplete="off"
                  icon="key"
                  label="Recovered flag"
                  onChange={(event) => setFlag(event.target.value)}
                  placeholder="MIRRAGE{...}"
                  value={flag}
                />
                <Button className="flag-submit" icon="send" loading={submitting} type="submit" variant="primary">
                  Submit flag
                </Button>
              </form>
            )}

            {feedback ? (
              <div className={`flag-feedback flag-feedback-${feedback.tone}`}>
                <Icon name={feedback.tone === 'success' ? 'check' : feedback.tone === 'error' ? 'info' : 'activity'} size={15} />
                <span>{feedback.message}</span>
              </div>
            ) : null}
          </Card>

          <Card className="detail-meta-card">
            <div className="platform-card-heading">
              <div>
                <span className="platform-card-kicker">Target metadata</span>
                <h2>Telemetry profile.</h2>
              </div>
            </div>
            <div className="detail-meta-list">
              <DetailMeta label="Category" value={challenge.category} />
              <DetailMeta label="Target Host" value={currentMirageIp || '10.42.0.x'} />
              <DetailMeta label="Network" value="10.42.0.0/16" />
              <DetailMeta label="VPN Required" value="OpenVPN Tunnel" />
              <DetailMeta label="Difficulty" value={challenge.difficulty} />
              <DetailMeta label="Points" value={`${challenge.points} pts`} />
            </div>
            <ProgressBar label="Community solve rate" tone={challenge.difficulty === 'Expert' ? 'orange' : 'blue'} value={challenge.solveRate} />
          </Card>
        </aside>
      </div>
    </div>
  );
}

function difficultyTone(difficulty: Difficulty): 'lime' | 'orange' | 'red' | 'purple' {
  return difficulty === 'Easy' ? 'lime' : difficulty === 'Medium' ? 'orange' : difficulty === 'Hard' ? 'red' : 'purple';
}

function DetailMeta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
