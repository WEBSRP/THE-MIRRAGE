import { Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { EmptyState, ProgressBar } from '../components/ui';
import { InteractiveNetworkScene } from '../design-system/InteractiveVisuals';
import { useApp } from '../state/AppState';
import './dashboard-space.css';

export function DashboardPage() {
  const { user, challenges, solvedChallengeIds, sessions, activities, vpn } = useApp();
  const activeSession = sessions.find((session) => ['starting', 'ready', 'stopping'].includes(session.status));
  const solved = challenges.filter((challenge) => solvedChallengeIds.includes(challenge.id));
  const available = challenges.filter((challenge) => !solvedChallengeIds.includes(challenge.id));
  const activeCount = sessions.filter((session) => ['starting', 'ready'].includes(session.status)).length;
  const nextTarget = available[0];
  const completion = challenges.length ? (solved.length / challenges.length) * 100 : 0;
  const vpnLabel = {
    connected: 'Connected',
    connecting: 'Connecting',
    disconnected: 'Disconnected',
    error: 'Connection error',
  }[vpn.status];

  return (
    <div className="platform-page dashboard-space">
      <header className="platform-page-header dashboard-space-welcome">
        <div>
          <span className="platform-eyebrow">Welcome back, {user.username}</span>
          <h1>Stay curious.<br /><em>Look closer.</em></h1>
          <p>One target at a time. Follow the signal.</p>
        </div>
      </header>

      <dl aria-label="Range overview" className="dashboard-space-metrics">
        <div className="dashboard-space-metric">
          <dt>Challenges solved</dt>
          <dd>
            <strong>{solved.length.toString().padStart(2, '0')}</strong>
            <span>of {challenges.length} targets</span>
          </dd>
        </div>
        <div className="dashboard-space-metric">
          <dt>Range points</dt>
          <dd>
            <strong>{user.points.toLocaleString()}</strong>
            <span>Rank #{user.rank} this week</span>
          </dd>
        </div>
        <div className="dashboard-space-metric">
          <dt>Active sessions</dt>
          <dd>
            <strong>{activeCount.toString().padStart(2, '0')}</strong>
            <span>{activeSession?.status === 'stopping' ? 'Shutdown in progress' : 'Simulated labs'}</span>
          </dd>
        </div>
        <div className="dashboard-space-metric dashboard-space-vpn">
          <dt>
            <Link className="dashboard-space-link" to="/vpn">
              VPN workspace <Icon name="arrow-up-right" size={13} />
            </Link>
          </dt>
          <dd>
            <strong className={vpn.status === 'connected' ? 'dashboard-space-connected' : undefined}>
              {vpnLabel}
            </strong>
            <span>Simulated{vpn.status === 'connected' && vpn.ip ? ` · ${vpn.ip}` : ' tunnel'}</span>
          </dd>
        </div>
      </dl>

      <div className="dashboard-space-direction">
        <section aria-labelledby="dashboard-progress-title" className="dashboard-space-progress">
          <span className="platform-card-kicker">Operator progress</span>
          <h2 id="dashboard-progress-title">A little further.</h2>
          <div
            aria-label="Range completion"
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={Math.round(completion)}
            aria-valuetext={`${solved.length} of ${challenges.length} challenges solved`}
            role="progressbar"
          >
            <ProgressBar label="Range completion" value={completion} />
          </div>
          <p>{available.length} {available.length === 1 ? 'target' : 'targets'} remaining</p>
        </section>

        <section aria-labelledby="dashboard-next-title" className="dashboard-space-next">
          <span className="platform-card-kicker" id="dashboard-next-title">Suggested next target</span>
          {nextTarget ? (
            <>
              <h2>{nextTarget.title}</h2>
              <ul aria-label="Target details" className="dashboard-space-target-meta">
                <li>{nextTarget.difficulty}</li>
                <li>{nextTarget.category}</li>
                <li>{nextTarget.estimatedTime}</li>
                <li>{nextTarget.points} pts</li>
              </ul>
              <p className="dashboard-space-description">{nextTarget.description}</p>
              <Link
                aria-label={`Investigate ${nextTarget.title}`}
                className="ui-button ui-button-primary ui-button-medium dashboard-space-action"
                to={`/challenges/${nextTarget.id}`}
              >
                Investigate target <Icon name="arrow-right" size={15} />
              </Link>
            </>
          ) : (
            <div className="dashboard-space-empty">
              <EmptyState
                icon={challenges.length ? 'check' : 'search'}
                title={challenges.length ? 'Every target solved' : 'No targets available'}
                message={challenges.length
                  ? 'You have cleared the current catalog. Revisit a challenge whenever you like.'
                  : 'The current catalog is empty. Check back for your next investigation.'}
                action={(
                  <Link className="ui-button ui-button-secondary ui-button-medium" to="/challenges">
                    View catalog <Icon name="arrow-right" size={15} />
                  </Link>
                )}
              />
            </div>
          )}
        </section>
      </div>

      <section aria-label="Interactive simulated network" className="dashboard-space-network">
        <InteractiveNetworkScene />
      </section>

      <div className="dashboard-space-logbook">
        <section aria-labelledby="dashboard-session-title" className="dashboard-space-session">
          <div className="dashboard-space-section-heading">
            <h2 id="dashboard-session-title">Active session</h2>
            <Link className="dashboard-space-link" to="/sessions">
              {activeSession?.status === 'ready' ? 'Sessions / terminal' : 'All sessions'}
              <Icon name="arrow-up-right" size={14} />
            </Link>
          </div>
          {activeSession ? (
            <ActiveSessionSummary session={activeSession} />
          ) : (
            <div className="dashboard-space-empty">
              <EmptyState
                icon="server"
                title="Nothing running right now"
                message="Start a challenge session when you are ready to investigate. Labs are simulated."
              />
            </div>
          )}
        </section>

        <section aria-labelledby="dashboard-activity-title" className="dashboard-space-activity">
          <div className="dashboard-space-section-heading">
            <h2 id="dashboard-activity-title">Recent activity</h2>
            <span className="dashboard-space-note">Local only</span>
          </div>
          <ActivityList activities={activities.slice(0, 5)} />
        </section>
      </div>
    </div>
  );
}

function ActiveSessionSummary({ session }: { session: ReturnType<typeof useApp>['sessions'][number] }) {
  const statusLabel = {
    starting: 'Starting',
    ready: 'Ready',
    stopping: 'Stopping',
    stopped: 'Stopped',
    expired: 'Expired',
    error: 'Error',
  }[session.status];

  return (
    <div className="dashboard-space-session-summary">
      <div className="dashboard-space-session-meta">
        <span className="dashboard-space-session-status">{statusLabel}</span>
        <span>Simulated / {session.id.slice(-4)}</span>
      </div>
      <h3>{session.title}</h3>
      <p className="dashboard-space-session-address"><span>{session.target}</span><span>{session.ip}</span></p>
      {session.status === 'starting' ? (
        <div
          aria-label="Provisioning simulated environment"
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={session.progress}
          role="progressbar"
        >
          <ProgressBar label="Provisioning environment" value={session.progress} tone="blue" />
        </div>
      ) : (
        <p className="dashboard-space-note">
          {session.status === 'ready' ? 'Simulated environment ready for inspection.' : 'Simulated environment is shutting down.'}
        </p>
      )}
    </div>
  );
}

function ActivityList({ activities }: { activities: ReturnType<typeof useApp>['activities'] }) {
  if (!activities.length) {
    return (
      <div className="dashboard-space-empty">
        <EmptyState icon="activity" title="No activity yet" message="Actions you take in the simulation will appear here." />
      </div>
    );
  }

  return (
    <ul className="dashboard-space-activity-list">
      {activities.map((activity) => (
        <li key={activity.id}>
          <span aria-hidden="true" className={`dashboard-space-activity-dot dashboard-space-activity-dot-${activity.tone}`} />
          <div>
            <strong>{activity.title}</strong>
            <p>{activity.detail}</p>
          </div>
          <time>{activity.timestamp}</time>
        </li>
      ))}
    </ul>
  );
}
