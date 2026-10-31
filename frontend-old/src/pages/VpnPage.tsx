import { useState, useEffect } from 'react';
import { getVpnStatus, downloadVpnConfig, downloadSignalConfig, type VpnStatus } from '../services/vpnService';

type Platform = 'windows' | 'linux' | 'macos';

/**
 * VpnPage — VPN & Signal management page.
 * Shows connection status, download buttons, and a responsive instruction panel.
 */
export function VpnPage() {
  const [vpnStatus, setVpnStatus] = useState<VpnStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingVpn, setDownloadingVpn] = useState(false);
  const [downloadingSignal, setDownloadingSignal] = useState(false);
  const [activePlatform, setActivePlatform] = useState<Platform>('windows');

  useEffect(() => {
    async function load() {
      try {
        const status = await getVpnStatus();
        setVpnStatus(status);
      } catch {
        // VPN status might not be available
      }
      setLoading(false);
    }
    load();
  }, []);

  const handleDownloadVpn = async () => {
    setDownloadingVpn(true);
    try {
      await downloadVpnConfig();
    } catch {
      // Handle silently
    }
    setDownloadingVpn(false);
  };

  const handleDownloadSignal = async () => {
    setDownloadingSignal(true);
    try {
      await downloadSignalConfig();
    } catch {
      // Handle silently
    }
    setDownloadingSignal(false);
  };

  const indicatorColor = vpnStatus?.indicator === 'connected'
    ? 'bg-[var(--success)]'
    : vpnStatus?.indicator === 'standby'
      ? 'bg-[var(--accent)]'
      : 'bg-[var(--text-faint)]';

  return (
    <div className="max-w-5xl">
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-[var(--text)] mb-1">VPN & Signal</h1>
        <p className="text-[var(--text-muted)] text-sm">Manage your connection to the MIRRAGE network.</p>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 lg:gap-12">
        {/* LEFT COLUMN - Existing Controls */}
        <div className="w-full lg:w-[400px] shrink-0">
          {/* VPN Status */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5 mb-4">
            <div className="flex items-center justify-between mb-4">
              <p className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">VPN Status</p>
              {loading ? (
                <span className="text-[var(--text-faint)] text-xs animate-pulse-subtle">Loading...</span>
              ) : (
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${indicatorColor}`} />
                  <span className="text-xs text-[var(--text-muted)]">
                    {vpnStatus?.is_connected ? 'Connected' : 'Not Connected'}
                  </span>
                </div>
              )}
            </div>

            {vpnStatus?.assigned_ip && (
              <div className="flex justify-between text-[12px] mb-2">
                <span className="text-[var(--text-faint)]">Assigned IP</span>
                <span className="font-mono text-[var(--text)]">{vpnStatus.assigned_ip}</span>
              </div>
            )}

            <button
              onClick={handleDownloadVpn}
              disabled={downloadingVpn}
              className="btn-primary w-full mt-3 text-xs"
            >
              {downloadingVpn ? 'Downloading...' : 'Download VPN Profile'}
            </button>
          </div>

          {/* Signal */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">Signal</p>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-[var(--success)]" />
                <span className="text-xs text-[var(--text-muted)]">Available</span>
              </div>
            </div>

            <p className="text-[var(--text-muted)] text-sm mb-3">
              Download Signal to get your environment metadata and connection profile.
            </p>

            <button
              onClick={handleDownloadSignal}
              disabled={downloadingSignal}
              className="btn-outline w-full text-xs"
            >
              {downloadingSignal ? 'Downloading...' : 'Download Signal'}
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN - New Instructions Panel */}
        <div className="flex-1 bg-[var(--surface)] border border-[var(--border)] rounded p-6 lg:p-8">
          <h2 className="font-serif text-xl text-[var(--text)] mb-1">CONNECT YOUR VPN</h2>
          <p className="text-[var(--text-muted)] text-sm mb-6">Use the MIRRAGE .ovpn profile to enter the isolated environment.</p>

          {/* TABS */}
          <div className="flex gap-6 border-b border-[var(--border)] mb-6">
            <button 
              onClick={() => setActivePlatform('windows')}
              className={`pb-2 text-xs font-mono uppercase tracking-wider transition-colors border-b-2 -mb-[1px] ${
                activePlatform === 'windows' 
                  ? 'text-[var(--accent)] border-[var(--accent)]' 
                  : 'text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
              }`}
            >
              WINDOWS
            </button>
            <button 
              onClick={() => setActivePlatform('linux')}
              className={`pb-2 text-xs font-mono uppercase tracking-wider transition-colors border-b-2 -mb-[1px] ${
                activePlatform === 'linux' 
                  ? 'text-[var(--accent)] border-[var(--accent)]' 
                  : 'text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
              }`}
            >
              LINUX
            </button>
            <button 
              onClick={() => setActivePlatform('macos')}
              className={`pb-2 text-xs font-mono uppercase tracking-wider transition-colors border-b-2 -mb-[1px] ${
                activePlatform === 'macos' 
                  ? 'text-[var(--accent)] border-[var(--accent)]' 
                  : 'text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
              }`}
            >
              macOS
            </button>
          </div>

          {/* TAB CONTENT */}
          <div className="space-y-6 min-h-[240px]">
            {activePlatform === 'windows' && (
              <>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">01</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Install OpenVPN Connect</h3>
                    <p className="text-sm text-[var(--text-muted)]">Install the official OpenVPN Connect client.</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">02</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Import your profile</h3>
                    <p className="text-sm text-[var(--text-muted)]">
                      Open OpenVPN Connect → Import Profile → File, then select the downloaded <code className="font-mono text-[11px] bg-[var(--surface-alt)] px-1 py-0.5 rounded text-[var(--text)]">.ovpn</code> file.
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">03</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Connect</h3>
                    <p className="text-sm text-[var(--text-muted)]">Select the imported MIRRAGE profile and switch the connection ON.</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">04</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Verify</h3>
                    <p className="text-sm text-[var(--text-muted)]">Wait until OpenVPN shows CONNECTED. Return to MIRRAGE and continue to the environment.</p>
                  </div>
                </div>
              </>
            )}

            {activePlatform === 'linux' && (
              <>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">01</div>
                  <div className="w-full">
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Install OpenVPN</h3>
                    <p className="text-sm text-[var(--text-muted)] mb-2">Debian/Ubuntu:</p>
                    <div className="bg-[var(--bg)] border border-[var(--border)] rounded px-3 py-2 font-mono text-[11px] text-[var(--text)] overflow-x-auto">
                      sudo apt install openvpn
                    </div>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">02</div>
                  <div className="w-full">
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Connect with your profile</h3>
                    <p className="text-sm text-[var(--text-muted)] mb-2">From the directory containing the downloaded file:</p>
                    <div className="bg-[var(--bg)] border border-[var(--border)] rounded px-3 py-2 font-mono text-[11px] text-[var(--text)] overflow-x-auto">
                      sudo openvpn --config mirrage_username.ovpn
                    </div>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">03</div>
                  <div className="w-full">
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Wait for connection</h3>
                    <p className="text-sm text-[var(--text-muted)] mb-2">Wait for:</p>
                    <div className="bg-[var(--bg)] border border-[var(--border)] rounded px-3 py-2 font-mono text-[11px] text-[var(--text)] overflow-x-auto">
                      Initialization Sequence Completed
                    </div>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">04</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Keep the terminal running</h3>
                    <p className="text-sm text-[var(--text-muted)]">Leave OpenVPN running while playing. Open another terminal for SSH/Nmap/challenge activity.</p>
                  </div>
                </div>
              </>
            )}

            {activePlatform === 'macos' && (
              <>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">01</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Install OpenVPN Connect</h3>
                    <p className="text-sm text-[var(--text-muted)]">Install the official OpenVPN Connect client.</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">02</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Import your profile</h3>
                    <p className="text-sm text-[var(--text-muted)]">
                      Open OpenVPN Connect → Import Profile → File, then select the downloaded <code className="font-mono text-[11px] bg-[var(--surface-alt)] px-1 py-0.5 rounded text-[var(--text)]">.ovpn</code> file.
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">03</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Connect</h3>
                    <p className="text-sm text-[var(--text-muted)]">Select the MIRRAGE profile and switch the VPN connection ON.</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="font-mono text-xs text-[var(--accent)] mt-0.5">04</div>
                  <div>
                    <h3 className="text-sm font-medium text-[var(--text)] mb-1">Verify</h3>
                    <p className="text-sm text-[var(--text-muted)]">Wait until OpenVPN shows CONNECTED, then return to MIRRAGE.</p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* SECURITY NOTE */}
          <div className="mt-8 pt-5 border-t border-[var(--border)]/50">
            <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-1">
              <strong className="text-[var(--text)] font-medium">Keep your .ovpn profile private.</strong> It contains credentials that are unique to your MIRRAGE session.
            </p>
            <p className="text-xs text-[var(--danger)] leading-relaxed">
              Do not share or commit the profile to Git.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
