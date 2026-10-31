import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { Badge, Button, Card, EmptyState, ProgressBar, StatusBadge } from '../components/ui';
import { useApp } from '../state/AppState';

type Diagnostic = { label: string; detail: string; status: 'idle' | 'running' | 'pass' | 'fail' };

export function VpnPage() {
  const { vpn, connectVpn, disconnectVpn, simulateVpnError, retryVpn, downloadVpnConfig } = useApp();
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<'client' | 'manual'>('client');
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([
    { label: 'Gateway reachability', detail: 'No test run yet', status: 'idle' },
    { label: 'Tunnel handshake', detail: 'No test run yet', status: 'idle' },
    { label: 'Lab route visibility', detail: 'No test run yet', status: 'idle' },
  ]);

  const duration = useDuration(vpn.connectedAt);
  const isConnected = vpn.status === 'connected';
  const isConnecting = vpn.status === 'connecting';
  const isError = vpn.status === 'error';

  const handleConnect = async () => { setBusy(true); if (isError) await retryVpn(); else await connectVpn(); setBusy(false); };
  const handleDisconnect = async () => { setBusy(true); await disconnectVpn(); setBusy(false); };
  const runDiagnostics = async () => {
    setDiagnostics((current) => current.map((item) => ({ ...item, status: 'running', detail: 'Checking simulated path…' })));
    await new Promise((resolve) => window.setTimeout(resolve, 900));
    setDiagnostics((current) => current.map((item, index) => ({ ...item, status: isError && index === 1 ? 'fail' : 'pass', detail: isError && index === 1 ? 'Gateway handshake timed out' : 'Response received in 24 ms' })));
  };

  return <div className="platform-page vpn-page"><div className="platform-page-header"><div><span className="platform-eyebrow">04 / connection layer</span><h1>VPN workspace</h1><p>Prepare a simulated tunnel into the private range. Nothing on this page connects to a real VPN.</p></div><Badge tone="orange" dot>Simulation only</Badge></div>
    <div className="vpn-layout"><Card className={`vpn-status-card vpn-status-${vpn.status}`}><div className="vpn-status-top"><div><span className="platform-card-kicker">Connection state</span><h2>{isConnected ? 'Tunnel is open.' : isConnecting ? 'Opening tunnel…' : isError ? 'Signal lost.' : 'Ready to connect.'}</h2></div><StatusBadge status={isConnected ? 'Connected' : isConnecting ? 'Connecting' : isError ? 'Connection error' : 'Disconnected'} /></div><div className="vpn-radar"><span className="vpn-radar-ring ring-one" /><span className="vpn-radar-ring ring-two" /><span className="vpn-radar-ring ring-three" /><span className="vpn-radar-sweep" /><span className="vpn-radar-core"><Icon name="vpn" size={27} /></span></div>{isConnecting ? <ProgressBar label="Negotiating simulated handshake" value={68} tone="orange" /> : isError ? <div className="vpn-error-copy"><Icon name="info" size={17} /><span>{vpn.lastError}</span></div> : <div className="vpn-status-copy">{isConnected ? 'Private lab routes are available in simulation mode.' : 'Connect when you want the platform to display a mock tunnel address.'}</div>}<div className="vpn-actions">{isConnected ? <Button loading={busy} onClick={handleDisconnect} variant="danger" icon="stop">Disconnect tunnel</Button> : <Button loading={busy} onClick={handleConnect} variant="primary" icon="vpn">{isError ? 'Retry connection' : 'Connect simulated VPN'}</Button>}{!isConnecting && !isConnected ? <Button onClick={simulateVpnError} size="small" variant="ghost">Simulate error</Button> : null}</div><div className="vpn-connection-details"><Detail label="Server" value={vpn.server} /><Detail label="Assigned IP" value={vpn.ip ?? '—'} /><Detail label="Duration" value={isConnected ? duration : '—'} /><Detail label="Tunnel type" value="Mock / local" /></div></Card><Card className="vpn-config-card"><div className="platform-card-heading"><div><span className="platform-card-kicker">Configuration</span><h2>Connect your client.</h2></div><Icon name="download" size={19} /></div><p>Download a harmless mock profile or follow the setup notes below. It is intentionally non-functional and cannot establish a real tunnel.</p><div className="vpn-tab-list" role="tablist">{(['client', 'manual'] as const).map((tab) => <button aria-selected={activeTab === tab} className={activeTab === tab ? 'is-active' : ''} key={tab} onClick={() => setActiveTab(tab)} role="tab" type="button">{tab === 'client' ? 'Client setup' : 'Manual notes'}</button>)}</div>{activeTab === 'client' ? <ol className="vpn-instructions"><li><span>01</span><p>Download the simulated profile to your device.</p></li><li><span>02</span><p>Open it in your preferred VPN client — it will not make a network request.</p></li><li><span>03</span><p>Return here and use the simulated connect control above.</p></li></ol> : <div className="vpn-manual-note"><Icon name="terminal" size={19} /><p><strong>Mock command</strong><code>mirrage vpn connect --profile demo</code><small>This renders instructions only. No command is executed.</small></p></div>}<Button className="vpn-download" onClick={downloadVpnConfig} variant="secondary" icon="download">Download mock profile</Button></Card></div>
    <div className="vpn-lower-grid"><Card><div className="platform-card-heading"><div><span className="platform-card-kicker">Diagnostics</span><h2>Check the signal.</h2></div><Button loading={diagnostics.some((item) => item.status === 'running')} onClick={runDiagnostics} size="small" variant="ghost" icon="activity">Run checks</Button></div><div className="diagnostic-list">{diagnostics.map((diagnostic) => <div className="diagnostic-row" key={diagnostic.label}><span className={`diagnostic-icon diagnostic-${diagnostic.status}`}><Icon name={diagnostic.status === 'pass' ? 'check' : diagnostic.status === 'fail' ? 'x' : diagnostic.status === 'running' ? 'loader' : 'circle'} size={14} /></span><span><strong>{diagnostic.label}</strong><small>{diagnostic.detail}</small></span><StatusBadge status={diagnostic.status === 'pass' ? 'Passed' : diagnostic.status === 'fail' ? 'Failed' : diagnostic.status === 'running' ? 'Running' : 'Not run'} /></div>)}</div></Card><Card><div className="platform-card-heading"><div><span className="platform-card-kicker">Connection history</span><h2>Recent signals.</h2></div></div><div className="vpn-history-list">{vpn.history.length ? vpn.history.slice(0, 5).map((item) => <div className="vpn-history-row" key={item.id}><span className={`activity-dot activity-dot-${item.tone}`} /><span><strong>{item.event}</strong><small>{item.detail}</small></span><time>{item.time}</time></div>) : <EmptyState icon="activity" title="No connection history" message="Simulated VPN events will appear here." />}</div></Card></div>
    <Card className="vpn-troubleshooting"><div className="troubleshooting-icon"><Icon name="help" size={21} /></div><div><span className="platform-card-kicker">Troubleshooting</span><h2>Something feel off?</h2><p>Run diagnostics first, then reset the simulated state. In a real deployment this is where client logs and gateway health would be reviewed.</p></div><Button onClick={runDiagnostics} variant="ghost" icon="refresh">Run diagnostics</Button></Card>
  </div>;
}

function Detail({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }

function useDuration(connectedAt: number | null) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!connectedAt) return undefined; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, [connectedAt]);
  if (!connectedAt) return '00:00:00';
  const seconds = Math.max(0, Math.floor((now - connectedAt) / 1000));
  return [Math.floor(seconds / 3600), Math.floor((seconds % 3600) / 60), seconds % 60].map((part) => part.toString().padStart(2, '0')).join(':');
}
