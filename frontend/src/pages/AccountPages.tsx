import { useState, type FormEvent } from 'react';
import { Icon } from '../components/Icon';
import { Badge, Button, Card, ConfirmDialog, TextField } from '../components/ui';
import { useApp, useTheme } from '../state/AppState';

export function ProfilePage() {
  const { user, updateUser, activities, solvedChallengeIds, logout, downloadVpnConfig } = useApp();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: user.name, username: user.username, email: user.email });
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const update = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const cancel = () => {
    setForm({ name: user.name, username: user.username, email: user.email });
    setFeedback(null);
    setEditing(false);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    const result = await updateUser(form);
    setSaving(false);
    if (!result.ok) {
      setFeedback({ tone: 'error', message: result.message ?? 'Unable to update profile.' });
    } else {
      setFeedback({ tone: 'success', message: 'Profile details saved.' });
      setEditing(false);
    }
  };

  const memberSince = user.created_at || user.createdAt || '2026-01-01';

  return (
    <div className="platform-page profile-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">06 / identity layer</span>
          <h1>Operator Profile</h1>
          <p>Your authenticated identity and range telemetry credentials.</p>
        </div>
        <Badge tone="lime" dot>Active Operator</Badge>
      </div>

      <div className="profile-layout">
        <Card className="profile-identity-card">
          <div className="profile-avatar-large">
            {user.username ? user.username.charAt(0).toUpperCase() : user.avatar}
          </div>
          <h2>{user.name || user.username}</h2>
          <p>@{user.username}</p>
          <Badge tone="lime" dot>{user.role || 'Operator'}</Badge>
          <div className="profile-member">
            <span>Member since</span>
            <strong>{formatDate(memberSince)}</strong>
          </div>
          <div className="profile-profile-note">
            <Icon name="shield" size={14} />
            <span>Authenticated cluster session active</span>
          </div>
        </Card>

        <Card className="profile-details-card">
          <div className="platform-card-heading">
            <div>
              <span className="platform-card-kicker">Account details</span>
              <h2>How the range knows you.</h2>
            </div>
            {!editing ? (
              <Button
                onClick={() => {
                  setFeedback(null);
                  setEditing(true);
                }}
                size="small"
                variant="secondary"
                icon="settings"
              >
                Edit details
              </Button>
            ) : null}
          </div>

          {feedback ? (
            <div className={`platform-inline-notice notice-${feedback.tone}`}>
              <Icon name={feedback.tone === 'success' ? 'check' : 'info'} size={15} /> {feedback.message}
            </div>
          ) : null}

          {editing ? (
            <form className="profile-form" onSubmit={save}>
              <TextField
                label="Full name"
                onChange={(event) => update('name', event.target.value)}
                required
                value={form.name}
              />
              <TextField
                label="Username"
                onChange={(event) => update('username', event.target.value)}
                required
                value={form.username}
              />
              <TextField
                label="Email address"
                onChange={(event) => update('email', event.target.value)}
                required
                type="email"
                value={form.email}
              />
              <div className="profile-form-actions">
                <Button onClick={cancel} type="button" variant="ghost">Cancel</Button>
                <Button loading={saving} type="submit" variant="primary" icon="check">Save changes</Button>
              </div>
            </form>
          ) : (
            <div className="profile-detail-list">
              <Detail label="Full name" value={user.name || user.username} />
              <Detail label="Username" value={`@${user.username}`} />
              <Detail label="Email address" value={user.email} />
              <Detail label="Account status" value={user.is_active !== false ? 'Active' : 'Inactive'} />
              <Detail label="User ID" value={user.id ? String(user.id) : 'usr_operator'} />
            </div>
          )}

          <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border)' }}>
            <Button onClick={logout} size="small" variant="ghost" icon="logout">
              Sign Out of Cluster
            </Button>
          </div>
        </Card>
      </div>

      <div className="profile-summary-grid">
        <Card>
          <div className="platform-card-heading">
            <div>
              <span className="platform-card-kicker">Account activity</span>
              <h2>Telemetry & Performance</h2>
            </div>
          </div>
          <div className="profile-metrics">
            <Metric label="Range points" value={user.points.toLocaleString()} />
            <Metric label="Current rank" value={`#${user.rank}`} />
            <Metric label="Challenges solved" value={solvedChallengeIds.length.toString().padStart(2, '0')} />
            <Metric label="Activity events" value={activities.length.toString().padStart(2, '0')} />
          </div>
        </Card>

        <Card className="profile-security-note">
          <div className="security-note-icon">
            <Icon name="lock" size={19} />
          </div>
          <div>
            <span className="platform-card-kicker">Security & Tunnel</span>
            <h3>Cryptographic Certificate Bound</h3>
            <p style={{ marginBottom: '1rem' }}>
              Your account has a dedicated OpenVPN profile. Connect through your VPN client to access the assigned challenge environment.
            </p>
            <Button onClick={() => downloadVpnConfig()} size="small" variant="secondary" icon="download">
              Download Active .ovpn Profile
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { user, logout, pushToast } = useApp();
  const { theme, toggleTheme } = useTheme();
  const [notifications, setNotifications] = useState({
    activity: true,
    targets: true,
    product: false,
  });
  const [confirmLogout, setConfirmLogout] = useState(false);

  const handleClearCache = () => {
    window.localStorage.removeItem('mirrage_token');
    pushToast('Cache cleared', 'Application cache and session tokens have been cleared.', 'info');
    logout();
  };

  return (
    <div className="platform-page settings-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">07 / control surface</span>
          <h1>Settings</h1>
          <p>Configure interface atmosphere, notifications, and security preferences.</p>
        </div>
        <Badge tone="lime" dot>Preferences Synced</Badge>
      </div>

      <div className="settings-layout">
        <div className="settings-main">
          <Card>
            <div className="settings-section-heading">
              <div>
                <span className="platform-card-kicker">Appearance</span>
                <h2>Set the atmosphere.</h2>
              </div>
              <Icon name={theme === 'dark' ? 'moon' : 'sun'} size={19} />
            </div>
            <div className="settings-choice-row">
              <div>
                <strong>Color theme</strong>
                <p>Switch between the MIRRAGE night signal and high-clarity day mode.</p>
              </div>
              <button
                aria-pressed={theme === 'light'}
                className="theme-choice"
                onClick={toggleTheme}
                type="button"
              >
                <span className={theme === 'dark' ? 'is-active' : ''}>
                  <Icon name="moon" size={14} /> Dark
                </span>
                <span className={theme === 'light' ? 'is-active' : ''}>
                  <Icon name="sun" size={14} /> Light
                </span>
              </button>
            </div>
          </Card>

          <Card>
            <div className="settings-section-heading">
              <div>
                <span className="platform-card-kicker">Notifications</span>
                <h2>Choose what reaches you.</h2>
              </div>
              <Icon name="bell" size={19} />
            </div>
            <div className="settings-toggle-list">
              <ToggleRow
                checked={notifications.activity}
                detail="Show real-time activity and session lifecycle notices."
                label="Activity updates"
                onChange={() => setNotifications((current) => ({ ...current, activity: !current.activity }))}
              />
              <ToggleRow
                checked={notifications.targets}
                detail="Highlight when new challenges and isolated environments rotate into the range."
                label="New target signals"
                onChange={() => setNotifications((current) => ({ ...current, targets: !current.targets }))}
              />
              <ToggleRow
                checked={notifications.product}
                detail="Occasional system announcements and field guide updates."
                label="Product notes"
                onChange={() => setNotifications((current) => ({ ...current, product: !current.product }))}
              />
            </div>
          </Card>
        </div>

        <aside className="settings-aside">
          <Card className="settings-info-card">
            <span className="settings-aside-icon">
              <Icon name="shield" size={21} />
            </span>
            <span className="platform-card-kicker">Security posture</span>
            <h2>Isolated Pod Boundary</h2>
            <p>
              Your account communicates with the MIRRAGE cluster over secure TLS. Container environments run in ephemeral micro-namespaces.
            </p>
            <Badge tone="lime" dot>TLS 1.3 / OpenVPN</Badge>
          </Card>

          <Card className="settings-danger-card">
            <span className="platform-card-kicker">Session Management</span>
            <h3>Terminate Session</h3>
            <p>Sign out of the current cluster session and clear cached credentials.</p>
            <Button onClick={() => setConfirmLogout(true)} size="small" variant="danger" icon="logout">
              Sign Out Everywhere
            </Button>
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        confirmLabel="Sign Out"
        danger
        message={`Are you sure you want to end your active session as @${user.username}? You will need to log back in to access isolated labs.`}
        onCancel={() => setConfirmLogout(false)}
        onConfirm={handleClearCache}
        open={confirmLogout}
        title="Sign Out of MIRRAGE?"
      />
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ToggleRow({
  checked,
  label,
  detail,
  onChange,
}: {
  checked: boolean;
  label: string;
  detail: string;
  onChange: () => void;
}) {
  return (
    <label className="settings-toggle-row">
      <span>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
      <input checked={checked} onChange={onChange} type="checkbox" />
      <span className="toggle-track">
        <span />
      </span>
    </label>
  );
}

function formatDate(value: string) {
  try {
    const d = value.includes('T') ? new Date(value) : new Date(`${value}T12:00:00`);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return value;
  }
}
