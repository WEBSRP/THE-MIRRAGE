import { Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { EmptyState, ProgressBar } from '../components/ui';
import { InteractiveNetworkScene } from '../design-system/InteractiveVisuals';
import { useApp } from '../state/AppState';
import './dashboard-space.css';

export function DashboardPage() {
  const { user, challenges, solvedChallengeIds, activities, vpnTelemetry, activeSessionData } = useApp();
  const isSessionOnline = Boolean(activeSessionData && (activeSessionData.status === 'ready' || activeSessionData.status === 'active'));
  const isSessionInitializing = activeSessionData?.status === 'initializing' || activeSessionData?.status === 'provisioning';

  const solved = challenges.filter((challenge) =>
    solvedChallengeIds.includes(challenge.slug) || solvedChallengeIds.includes(challenge.id) || challenge.is_solved
  );
  const available = challenges.filter((challenge) =>
    !solvedChallengeIds.includes(challenge.slug) && !solvedChallengeIds.includes(challenge.id) && !challenge.is_solved
  );
  const activeCount = isSessionOnline || isSessionInitializing ? 1 : 0;
  const nextTarget = available[0] || challenges[0];
  const completion = challenges.length ? (solved.length / challenges.length) * 100 : 0;
  const isVpnConnected = Boolean(vpnTelemetry?.is_connected);

  return (
    <div className="platform-page dashboard-space">
      <header className="platform-page-header dashboard-space-welcome">
        <div>
          <span className="platform-eyebrow">Welcome back, {user.username}</span>
          <h1>Stay curious.<br /><em>Look closer.</em></h1>
          <p>Dual-container Kubernetes targets with deception honeypots. Follow the signal.</p>
        </div>
      </header>

      <dl aria-label="Range overview" className="dashboard-space-metrics">
        <div className="dashboard-space-metric">
          <dt>Challenges solved</dt>
          <dd>
            <strong>{solved.length.toString().padStart(2, '0')}</strong>
            <span>of {challenges.length} active targets</span>
          </dd>
        </div>
        <div className="dashboard-space-metric">
          <dt>Range points</dt>
          <dd>
            <strong>{user.points.toLocaleString()}</strong>
            <span>Rank #{user.rank || 1} standing</span>
          </dd>
        </div>
        <div className="dashboard-space-metric">
          <dt>Active sessions</dt>
          <dd>
            <strong>{activeCount.toString().padStart(2, '0')}</strong>
            <span>{isSessionOnline ? 'Pod online' : isSessionInitializing ? 'Pod provisioning' : 'Standby'}</span>
          </dd>
        </div>
        <div className="dashboard-space-metric dashboard-space-vpn">
          <dt>
            <Link className="dashboard-space-link" to="/vpn">
              VPN workspace <Icon name="arrow-up-right" size={13} />
            </Link>
          </dt>
          <dd>
            <strong className={isVpnConnected ? 'dashboard-space-connected' : undefined}>
              {isVpnConnected ? 'Connected' : 'Standby'}
            </strong>
            <span>{isVpnConnected && vpnTelemetry?.assigned_ip ? vpnTelemetry.assigned_ip : 'OpenVPN tunnel'}</span>
          </dd>
        </div>
      </dl>

      <div className="dashboard-space-direction">
        <section aria-labelledby="dashboard-progress-title" className="dashboard-space-progress">
          <span className="platform-card-kicker">Operator progress</span>
          <h2 id="dashboard-progress-title">Breakthrough status.</h2>
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
          <p>{available.length} {available.length === 1 ? 'target' : 'targets'} remaining in active catalog</p>
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
                to={`/challenges/${nextTarget.slug || nextTarget.id}`}
              >
                Investigate target <Icon name="arrow-right" size={15} />
              </Link>
            </>
          ) : (
            <div className="dashboard-space-empty">
              <EmptyState
                action={
                  <Link className="ui-button ui-button-secondary ui-button-medium" to="/challenges">
                    View catalog <Icon name="arrow-right" size={15} />
                  </Link>
                }
                icon={challenges.length ? 'check' : 'search'}
                message={
                  challenges.length
                    ? 'You have solved the current targets. Revisit a challenge whenever you like.'
                    : 'The target catalog is loading.'
                }
                title={challenges.length ? 'All targets cleared' : 'Loading targets...'}
              />
            </div>
          )}
        </section>
      </div>

      <section aria-label="Interactive network visualization" className="dashboard-space-network">
        <InteractiveNetworkScene />
      </section>

      <div className="dashboard-space-logbook">
        <section aria-labelledby="dashboard-session-title" className="dashboard-space-session">
          <div className="dashboard-space-section-heading">
            <h2 id="dashboard-session-title">Environment pod</h2>
            <Link className="dashboard-space-link" to="/sessions">
              {isSessionOnline ? 'Console / terminal' : 'Session controls'}
              <Icon name="arrow-up-right" size={14} />
            </Link>
          </div>
          {activeSessionData && (isSessionOnline || isSessionInitializing) ? (
            <ActiveSessionSummary
              ip={activeSessionData.mirage_ip || '10.42.0.x'}
              isReady={isSessionOnline}
              sessionId={activeSessionData.session_id || 'active'}
              status={activeSessionData.status}
              title={challenges[0]?.title || 'Dual-Container Machine'}
            />
          ) : (
            <div className="dashboard-space-empty">
              <EmptyState
                action={
                  <Link className="ui-button ui-button-primary ui-button-medium" to="/sessions">
                    Start environment <Icon name="arrow-right" size={14} />
                  </Link>
                }
                icon="server"
                message="Launch a dedicated pod to spin up the honeypot and CTF endpoints."
                title="No active pod"
              />
            </div>
          )}
        </section>

        <section aria-labelledby="dashboard-activity-title" className="dashboard-space-activity">
          <div className="dashboard-space-section-heading">
            <h2 id="dashboard-activity-title">Audit & Telemetry Stream</h2>
            <span className="dashboard-space-note">Cluster Verified</span>
          </div>
          <ActivityList activities={activities.slice(0, 5)} />
        </section>
      </div>
    </div>
  );
}

function ActiveSessionSummary({
  title,
  ip,
  status,
  isReady,
  sessionId,
}: {
  title: string;
  ip: string;
  status: string;
  isReady: boolean;
  sessionId: string;
}) {
  return (
    <div className="dashboard-space-session-summary">
      <div className="dashboard-space-session-meta">
        <span className="dashboard-space-session-status">
          {isReady ? 'Online' : status === 'initializing' ? 'Provisioning' : status}
        </span>
        <span>Pod / {sessionId.slice(0, 8)}</span>
      </div>
      <h3>{title}</h3>
      <p className="dashboard-space-session-address">
        <span>Target host:</span>
        <strong style={{ color: 'var(--lime)', fontFamily: 'var(--font-mono)' }}>{ip}</strong>
      </p>
      {status === 'initializing' ? (
        <div
          aria-label="Provisioning cluster pod"
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={65}
          role="progressbar"
        >
          <ProgressBar label="Provisioning pod" tone="blue" value={65} />
        </div>
      ) : (
        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem' }}>
          <Link className="ui-button ui-button-secondary ui-button-small" to="/sessions">
            Open console <Icon name="terminal" size={13} />
          </Link>
          <Link className="ui-button ui-button-ghost ui-button-small" to="/vpn">
            VPN profile <Icon name="download" size={13} />
          </Link>
        </div>
      )}
    </div>
  );
}

function ActivityList({ activities }: { activities: ReturnType<typeof useApp>['activities'] }) {
  if (!activities.length) {
    return (
      <div className="dashboard-space-empty">
        <EmptyState
          icon="activity"
          message="Authentication events, environment launches, and flag breakthroughs will record here."
          title="No activity recorded"
        />
      </div>
    );
  }

  return (
    <ul className="dashboard-space-activity-list">
      {activities.map((activity) => (
        <li key={activity.id}>
          <span
            aria-hidden="true"
            className={`dashboard-space-activity-dot dashboard-space-activity-dot-${activity.tone}`}
          />
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
