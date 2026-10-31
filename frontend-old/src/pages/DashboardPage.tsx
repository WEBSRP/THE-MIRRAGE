import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { getVpnStatus, downloadVpnConfig, downloadSignalConfig, type VpnStatus } from '../services/vpnService';
import { getSessionStatus, type SessionStatusResponse } from '../services/sessionService';
import { getActivity, type ActivityLog } from '../services/activityService';

/** Maximum number of meaningful activity items to show on the dashboard. */
const ACTIVITY_DISPLAY_LIMIT = 5;

/**
 * Map raw backend event types to clean, human-readable labels.
 * Internal/technical events that shouldn't be shown on the dashboard
 * are mapped to `null`.
 */
const EVENT_LABEL_MAP: Record<string, string | null> = {
  session_start: 'Environment started',
  session_stop: 'Environment stopped',
  vpn_connect: 'VPN connected',
  vpn_disconnect: 'VPN disconnected',
  flag_submission: 'Flag submitted',
  ssh_auth_attempt: null,   // Internal — hide from dashboard
  ssh_command: null,         // Internal — hide from dashboard
  honeypot_trigger: null,    // Internal — hide from dashboard
  deception_discovery: null, // Internal — hide from dashboard
};

/** Returns a human-readable label for an activity event, or `null` to hide it. */
function getEventLabel(activity: ActivityLog): string | null {
  const mapped = EVENT_LABEL_MAP[activity.event_type];
  if (mapped !== undefined) return mapped;
  // Unknown event types — hide rather than expose raw names
  return null;
}

/**
 * Format a timestamp into a concise, human-readable relative string.
 *
 * Examples: "Just now", "2 min ago", "Today · 11:36", "Yesterday · 18:42"
 */
function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);

  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin} min ago`;

  // Check if same calendar day
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  if (isToday) return `Today · ${timeStr}`;

  // Check yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear();

  if (isYesterday) return `Yesterday · ${timeStr}`;

  // Older — show short date
  if (diffHours < 168) {
    // Within a week — show weekday
    const weekday = date.toLocaleDateString([], { weekday: 'short' });
    return `${weekday} · ${timeStr}`;
  }

  // Older than a week — show date
  const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  return `${dateStr} · ${timeStr}`;
}

/**
 * Process raw activity logs into clean, deduplicated dashboard items.
 *
 * - Filters out internal/technical events
 * - Collapses consecutive events of the same type
 * - Limits to ACTIVITY_DISPLAY_LIMIT items
 */
function processActivities(raw: ActivityLog[]): { label: string; timestamp: string; id: string }[] {
  const items: { label: string; timestamp: string; id: string }[] = [];

  for (const activity of raw) {
    const label = getEventLabel(activity);
    if (label === null) continue;

    // Deduplicate: skip if the previous visible item has the same label
    if (items.length > 0 && items[items.length - 1].label === label) continue;

    items.push({
      label,
      timestamp: activity.timestamp,
      id: activity.id,
    });

    if (items.length >= ACTIVITY_DISPLAY_LIMIT) break;
  }

  return items;
}

export function DashboardPage() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();

  const [vpnStatus, setVpnStatus] = useState<VpnStatus | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatusResponse | null>(null);
  const [activities, setActivities] = useState<ActivityLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const [vpnRes, sessionRes, activityRes] = await Promise.all([
          getVpnStatus().catch(() => null),
          getSessionStatus().catch(() => null),
          getActivity().catch(() => [])
        ]);

        if (mounted) {
          setVpnStatus(vpnRes);
          setSessionStatus(sessionRes);
          setActivities(activityRes || []);
          setIsLoading(false);
        }
      } catch {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      mounted = false;
    };
  }, []);

  const handleDownloadVpn = async () => {
    try {
      await downloadVpnConfig();
    } catch (error) {
      console.error('Failed to download VPN config', error);
    }
  };

  const handleDownloadSignal = async () => {
    try {
      await downloadSignalConfig();
    } catch (error) {
      console.error('Failed to download Signal config', error);
    }
  };

  const greeting = theme === 'morning' ? 'Good morning' : 'Good evening';

  // Environment ID generation or placeholder
  const envId = sessionStatus?.session_id
    ? `MIRAGE-${sessionStatus.session_id.substring(0, 4).toUpperCase()}`
    : 'MIRAGE-7F31';

  const isSessionOnline = !!sessionStatus?.is_ready && (sessionStatus?.status === 'active' || sessionStatus?.status === 'running' || sessionStatus?.status === 'ready');
  const isSessionInitializing = sessionStatus?.status === 'initializing' || sessionStatus?.status === 'provisioning' || sessionStatus?.status === 'pending';
  const envIp = isSessionOnline && sessionStatus?.mirage_ip ? sessionStatus.mirage_ip : null;

  const displayActivities = processActivities(activities);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl text-[var(--text)]">
          {greeting}, {user?.username || 'Explorer'}.
        </h1>
        <p className="text-[var(--text-muted)] text-sm">
          Ready to uncover what lies beneath?
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Environment Status Card */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5 flex flex-col gap-4 lg:col-span-2">
          <div className="flex justify-between items-start">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
                YOUR ENVIRONMENT
              </span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-lg text-[var(--text)]">{envId}</span>
                {isSessionOnline ? (
                  <span className="text-[var(--success)] text-xs flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)] inline-block"></span>
                    Online
                  </span>
                ) : isSessionInitializing ? (
                  <span className="text-[var(--accent)] text-xs flex items-center gap-1 font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse inline-block"></span>
                    Initializing...
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)] text-xs flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] inline-block"></span>
                    Offline
                  </span>
                )}
              </div>
              {isSessionOnline && envIp && (
                <span className="font-mono text-sm text-[var(--text-muted)]">
                  {envIp}
                </span>
              )}
            </div>

            <div className="flex flex-col items-end gap-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[var(--text-muted)]">VPN:</span>
                <span className={vpnStatus?.is_connected ? 'text-[var(--success)]' : 'text-[var(--text)]'}>
                  {vpnStatus?.is_connected ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[var(--text-muted)]">Signal:</span>
                <span className="text-[var(--text)]">Available</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 mt-2">
            {!isSessionOnline && !isSessionInitializing && (
              <button
                onClick={() => navigate('/session')}
                className="px-3 py-1.5 bg-[var(--accent)] text-[#000000] rounded text-xs font-medium hover:opacity-90 transition-opacity cursor-pointer"
              >
                Start Environment
              </button>
            )}
            {isSessionInitializing && (
              <button
                onClick={() => navigate('/session')}
                className="px-3 py-1.5 bg-[var(--accent)] text-[#000000] rounded text-xs font-medium hover:opacity-90 transition-opacity cursor-pointer font-mono"
              >
                View Console (Initializing)
              </button>
            )}
            {isSessionOnline && (
              <button
                onClick={() => navigate('/session')}
                className="px-3 py-1.5 bg-[var(--accent)] text-[#000000] rounded text-xs font-medium hover:opacity-90 transition-opacity cursor-pointer"
              >
                Environment Console
              </button>
            )}
            {isSessionOnline && (
              <button
                onClick={handleDownloadVpn}
                className="px-3 py-1.5 border border-[var(--border)] text-[var(--text)] rounded text-xs font-medium hover:bg-[var(--surface)] transition-colors cursor-pointer"
              >
                Download VPN Profile
              </button>
            )}
            <button
              onClick={handleDownloadSignal}
              className="px-3 py-1.5 border border-[var(--border)] text-[var(--text)] rounded text-xs font-medium hover:bg-[var(--surface)] transition-colors cursor-pointer"
            >
              Download Signal
            </button>
          </div>
        </div>

        {/* Explore Challenges Card */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5 flex flex-col justify-between gap-4">
          <div className="flex flex-col gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
              TRAINING
            </span>
            <p className="text-sm text-[var(--text)]">
              Step into realistic scenarios and test your skills.
            </p>
          </div>
          <Link
            to="/challenges"
            className="text-[var(--accent)] text-sm hover:underline flex items-center gap-1 w-fit"
          >
            View Challenges →
          </Link>
        </div>
      </div>

      {/* Recent Activity Section */}
      <section className="flex flex-col gap-4">
        <h2 className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
          RECENT ACTIVITY
        </h2>

        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-1">
          {isLoading ? (
            <div className="p-4 text-sm text-[var(--text-muted)] text-center">Loading activity...</div>
          ) : displayActivities.length > 0 ? (
            <ul className="flex flex-col">
              {displayActivities.map((item, idx) => (
                <li
                  key={item.id}
                  className={`flex items-center gap-3 px-3 py-2.5 ${idx !== displayActivities.length - 1 ? 'border-b border-[var(--border)]' : ''}`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] shrink-0"></span>
                  <span className="text-sm text-[var(--text)] flex-1">{item.label}</span>
                  <span className="font-mono text-[11px] text-[var(--text-faint)] whitespace-nowrap">
                    {formatRelativeTime(item.timestamp)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-8 text-sm text-[var(--text-muted)] text-center flex flex-col items-center gap-2">
              <span className="font-mono text-xs opacity-50">NO ACTIVITY</span>
              <p>Your recent actions will appear here.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
