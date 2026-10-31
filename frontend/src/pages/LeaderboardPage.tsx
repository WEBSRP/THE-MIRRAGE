import { Icon } from '../components/Icon';
import { Badge, Card, EmptyState } from '../components/ui';
import { useApp } from '../state/AppState';

export function LeaderboardPage() {
  const { leaderboard, user } = useApp();

  return (
    <div className="platform-page leaderboard-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">05 / global standings</span>
          <h1>Leaderboard</h1>
          <p>Top operators ranked by confirmed signal breakthroughs and range points.</p>
        </div>
        <div className="challenge-header-stat">
          <strong>#{user.rank || 1}</strong>
          <span>your<br />standing</span>
        </div>
      </div>

      <Card padding="none" style={{ overflow: 'hidden' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '4rem 1fr 6rem 6rem',
          padding: '0.875rem 1.25rem',
          borderBottom: '1px solid var(--line)',
          fontSize: '0.6875rem',
          fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: 'var(--muted)',
          backgroundColor: 'var(--panel-deep)',
        }}>
          <span>Rank</span>
          <span>Operator</span>
          <span style={{ textAlign: 'right' }}>Solved</span>
          <span style={{ textAlign: 'right' }}>Points</span>
        </div>

        {leaderboard.length === 0 ? (
          <EmptyState
            icon="shield"
            title="No rankings recorded yet"
            message="Complete challenge objectives to register your score on the range leaderboard."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {leaderboard.map((entry) => {
              const isSelf = entry.isCurrentUser || entry.username === user.username;
              return (
                <div
                  key={entry.rank}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '4rem 1fr 6rem 6rem',
                    alignItems: 'center',
                    padding: '1rem 1.25rem',
                    borderBottom: '1px solid var(--line-soft, var(--line))',
                    backgroundColor: isSelf ? 'var(--lime-soft, rgba(34, 197, 94, 0.05))' : 'transparent',
                    transition: 'background-color 0.15s ease',
                  }}
                >
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.875rem',
                    color: entry.rank <= 3 ? 'var(--lime)' : 'var(--muted)',
                    fontWeight: 600,
                  }}>
                    {String(entry.rank).padStart(2, '0')}
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      backgroundColor: isSelf ? 'var(--lime)' : 'var(--line)',
                      color: isSelf ? '#000000' : 'var(--white)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                    }}>
                      {(entry.username.charAt(0) || 'O').toUpperCase()}
                    </div>
                    <div>
                      <strong style={{ display: 'block', fontSize: '0.875rem', color: 'var(--white)' }}>
                        {entry.username}
                        {isSelf && (
                          <span style={{ marginLeft: '0.5rem' }}>
                            <Badge tone="lime">You</Badge>
                          </span>
                        )}
                      </strong>
                    </div>
                  </div>

                  <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.875rem', color: 'var(--muted)' }}>
                    {entry.solved}
                  </span>

                  <span style={{
                    textAlign: 'right',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    color: 'var(--lime)',
                  }}>
                    {entry.points} pts
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <div style={{ marginTop: '2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--muted)', fontSize: '0.75rem' }}>
        <Icon name="info" size={14} />
        <span>Scores synchronize whenever a confirmed flag is registered through the verification engine.</span>
      </div>
    </div>
  );
}
