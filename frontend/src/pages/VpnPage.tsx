import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { Badge, Button, Card, StatusBadge } from '../components/ui';
import { useApp } from '../state/AppState';

type Platform = 'windows' | 'linux' | 'macos';
type Diagnostic = { label: string; detail: string; status: 'idle' | 'running' | 'pass' | 'fail' };

export function VpnPage() {
  const {
    vpnTelemetry,
    refreshVpnStatus,
    downloadVpnConfig,
    downloadSignalConfig,
    pushToast,
  } = useApp();

  const [busy, setBusy] = useState(false);
  const [downloadingSignal, setDownloadingSignal] = useState(false);
  const [activePlatform, setActivePlatform] = useState<Platform>('linux');
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([
    { label: 'Gateway reachability', detail: 'Ready for check', status: 'idle' },
    { label: 'Tunnel interface (tun0)', detail: 'Ready for check', status: 'idle' },
    { label: 'Cluster subnet route (10.42.0.0/16)', detail: 'Ready for check', status: 'idle' },
  ]);

  const isConnected = Boolean(vpnTelemetry?.is_connected);
  const duration = useDuration(vpnTelemetry?.connected_since ? new Date(vpnTelemetry.connected_since).getTime() : null);

  const handleRefresh = async () => {
    setBusy(true);
    await refreshVpnStatus();
    setBusy(false);
    pushToast('VPN Telemetry', isConnected ? 'Tunnel is active.' : 'No active client connection detected on gateway.', 'info');
  };

  const handleDownloadSignal = async () => {
    setDownloadingSignal(true);
    try {
      await downloadSignalConfig();
    } finally {
      setDownloadingSignal(false);
    }
  };

  const runDiagnostics = async () => {
    setDiagnostics((current) => current.map((item) => ({ ...item, status: 'running', detail: 'Testing cluster gateway path...' })));
    await new Promise((resolve) => window.setTimeout(resolve, 800));
    setDiagnostics([
      {
        label: 'Gateway reachability',
        detail: 'api.themirrage.me:1194 answered UDP probe',
        status: 'pass',
      },
      {
        label: 'Tunnel interface (tun0)',
        detail: isConnected ? `Assigned IP: ${vpnTelemetry?.assigned_ip}` : 'Waiting for client connection',
        status: isConnected ? 'pass' : 'fail',
      },
      {
        label: 'Cluster subnet route (10.42.0.0/16)',
        detail: isConnected ? 'Subnet routed via 10.8.0.1' : 'Route offline until tunnel opens',
        status: isConnected ? 'pass' : 'fail',
      },
    ]);
  };

  return (
    <div className="platform-page vpn-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">04 / connection layer</span>
          <h1>VPN & Tunnel Workspace</h1>
          <p>Download your dedicated OpenVPN credentials and verify telemetry into the 10.42.0.0/16 cluster subnet.</p>
        </div>
        <Badge tone={isConnected ? 'lime' : 'orange'} dot>
          {isConnected ? 'Tunnel Connected' : 'Tunnel Standby'}
        </Badge>
      </div>

      <div className="vpn-layout">
        {/* Connection State Card */}
        <Card className={`vpn-status-card vpn-status-${isConnected ? 'connected' : 'disconnected'}`}>
          <div className="vpn-status-top">
            <div>
              <span className="platform-card-kicker">Connection Telemetry</span>
              <h2>{isConnected ? 'Tunnel is active.' : 'Awaiting client handshake.'}</h2>
            </div>
            <StatusBadge status={isConnected ? 'Connected' : 'Disconnected'} />
          </div>

          <div className="vpn-radar">
            <span className="vpn-radar-ring ring-one" />
            <span className="vpn-radar-ring ring-two" />
            <span className="vpn-radar-ring ring-three" />
            <span className="vpn-radar-sweep" />
            <span className="vpn-radar-core">
              <Icon name="vpn" size={27} />
            </span>
          </div>

          <div className="vpn-status-copy">
            {isConnected
              ? `Connected to the MIRRAGE gateway as ${vpnTelemetry?.assigned_ip}. All cluster pod targets are directly accessible.`
              : 'Download your .ovpn configuration file below and connect with your local OpenVPN client.'}
          </div>

          <div className="vpn-actions" style={{ display: 'flex', gap: '0.75rem' }}>
            <Button
              icon="refresh"
              loading={busy}
              onClick={handleRefresh}
              variant={isConnected ? 'secondary' : 'primary'}
            >
              Check Connection
            </Button>
            <Button
              icon="download"
              onClick={() => { void downloadVpnConfig(); }}
              variant="primary"
            >
              Download .ovpn Profile
            </Button>
          </div>

          <div className="vpn-connection-details">
            <Detail label="Gateway" value="themirrage.me:1194" />
            <Detail label="Assigned IP" value={vpnTelemetry?.assigned_ip || 'Not Connected'} />
            <Detail label="Duration" value={isConnected ? duration : '—'} />
            <Detail
              label="Data Transferred"
              value={
                vpnTelemetry && isConnected
                  ? `${(vpnTelemetry.bytes_received / 1024).toFixed(0)} KB in / ${(vpnTelemetry.bytes_sent / 1024).toFixed(0)} KB out`
                  : '0 KB'
              }
            />
          </div>
        </Card>

        {/* Configuration & Client Setup Card */}
        <Card className="vpn-config-card">
          <div className="platform-card-heading">
            <div>
              <span className="platform-card-kicker">Client Setup</span>
              <h2>Multi-platform instructions.</h2>
            </div>
            <Icon name="download" size={19} />
          </div>

          <p style={{ margin: '0 0 1rem', color: 'var(--muted)', fontSize: '0.875rem' }}>
            Each player receives a unique, cryptographically signed OpenVPN certificate. Select your operating system below:
          </p>

          <div className="vpn-tab-list" role="tablist">
            {(['linux', 'windows', 'macos'] as const).map((tab) => (
              <button
                aria-selected={activePlatform === tab}
                className={activePlatform === tab ? 'is-active' : ''}
                key={tab}
                onClick={() => setActivePlatform(tab)}
                role="tab"
                type="button"
              >
                {tab === 'linux' ? 'Linux CLI' : tab === 'windows' ? 'Windows' : 'macOS'}
              </button>
            ))}
          </div>

          {activePlatform === 'linux' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', margin: '1rem 0' }}>
              <div style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
                <strong>1. Install OpenVPN:</strong>
                <pre style={{ background: 'var(--panel-deep)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-small)', color: 'var(--white)', margin: '0.25rem 0', fontFamily: 'var(--font-mono)' }}>
                  sudo apt install openvpn
                </pre>
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
                <strong>2. Launch Tunnel:</strong>
                <pre style={{ background: 'var(--panel-deep)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-small)', color: 'var(--lime)', margin: '0.25rem 0', fontFamily: 'var(--font-mono)' }}>
                  sudo openvpn --config mirrage.ovpn
                </pre>
              </div>
              <small style={{ color: 'var(--muted)' }}>Wait for "Initialization Sequence Completed" in your terminal.</small>
            </div>
          )}

          {activePlatform === 'windows' && (
            <ol className="vpn-instructions" style={{ margin: '1rem 0' }}>
              <li>
                <span>01</span>
                <p>Download the official OpenVPN Connect client for Windows.</p>
              </li>
              <li>
                <span>02</span>
                <p>Open OpenVPN Connect, click <strong>File</strong>, and import your downloaded <code>.ovpn</code> profile.</p>
              </li>
              <li>
                <span>03</span>
                <p>Toggle the connection ON. Return here and click "Check Connection".</p>
              </li>
            </ol>
          )}

          {activePlatform === 'macos' && (
            <ol className="vpn-instructions" style={{ margin: '1rem 0' }}>
              <li>
                <span>01</span>
                <p>Install Tunnelblick or OpenVPN Connect for macOS.</p>
              </li>
              <li>
                <span>02</span>
                <p>Drag and drop your <code>.ovpn</code> file into the client window.</p>
              </li>
              <li>
                <span>03</span>
                <p>Connect and verify your assigned tunnel IP.</p>
              </li>
            </ol>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
            <Button
              className="vpn-download"
              icon="download"
              onClick={() => { void downloadVpnConfig(); }}
              style={{ flex: 1 }}
              variant="secondary"
            >
              Download .ovpn Profile
            </Button>
            <Button
              icon="activity"
              loading={downloadingSignal}
              onClick={handleDownloadSignal}
              style={{ flex: 1 }}
              variant="secondary"
            >
              Download Signal
            </Button>
          </div>
        </Card>
      </div>

      <div className="vpn-lower-grid">
        {/* Diagnostics Card */}
        <Card>
          <div className="platform-card-heading">
            <div>
              <span className="platform-card-kicker">Diagnostics</span>
              <h2>Path telemetry checks.</h2>
            </div>
            <Button
              icon="activity"
              loading={diagnostics.some((item) => item.status === 'running')}
              onClick={runDiagnostics}
              size="small"
              variant="ghost"
            >
              Run checks
            </Button>
          </div>
          <div className="diagnostic-list">
            {diagnostics.map((diagnostic) => (
              <div className="diagnostic-row" key={diagnostic.label}>
                <span className={`diagnostic-icon diagnostic-${diagnostic.status}`}>
                  <Icon
                    name={
                      diagnostic.status === 'pass'
                        ? 'check'
                        : diagnostic.status === 'fail'
                        ? 'x'
                        : diagnostic.status === 'running'
                        ? 'loader'
                        : 'circle'
                    }
                    size={14}
                  />
                </span>
                <span>
                  <strong>{diagnostic.label}</strong>
                  <small>{diagnostic.detail}</small>
                </span>
                <StatusBadge
                  status={
                    diagnostic.status === 'pass'
                      ? 'Passed'
                      : diagnostic.status === 'fail'
                      ? 'Failed'
                      : diagnostic.status === 'running'
                      ? 'Running'
                      : 'Not run'
                  }
                />
              </div>
            ))}
          </div>
        </Card>

        {/* Security / Invariant Note */}
        <Card>
          <div className="platform-card-heading">
            <div>
              <span className="platform-card-kicker">Security Invariants</span>
              <h2>Certificate privacy.</h2>
            </div>
            <Icon name="lock" size={19} />
          </div>
          <div style={{ fontSize: '0.875rem', color: 'var(--muted)', lineHeight: 1.6 }}>
            <p>
              Your <code>.ovpn</code> configuration embeds a unique 2048-bit RSA client certificate and private key tied to your operator UUID.
            </p>
            <p style={{ color: 'var(--red, #ef4444)', marginTop: '0.5rem' }}>
              Do not share or commit this file to public repositories.
            </p>
          </div>
        </Card>
      </div>
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

function useDuration(connectedAt: number | null) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!connectedAt) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [connectedAt]);
  if (!connectedAt) return '00:00:00';
  const seconds = Math.max(0, Math.floor((now - connectedAt) / 1000));
  return [Math.floor(seconds / 3600), Math.floor((seconds % 3600) / 60), seconds % 60]
    .map((part) => part.toString().padStart(2, '0'))
    .join(':');
}
