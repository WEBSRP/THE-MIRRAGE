import { useState } from 'react';
import { downloadVpnConfig, downloadSignalConfig } from '../services/vpnService';
import { Button } from './ui';
import { Icon } from './Icon';

export function StartPlayingModal({
  isOpen,
  onClose,
  onConfirm,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [downloadingVpn, setDownloadingVpn] = useState(false);
  const [downloadingSignal, setDownloadingSignal] = useState(false);

  if (!isOpen) return null;

  const handleDownloadVpn = async () => {
    setDownloadingVpn(true);
    try {
      await downloadVpnConfig();
    } catch {
      // Silent fail
    }
    setDownloadingVpn(false);
  };

  const handleDownloadSignal = async () => {
    setDownloadingSignal(true);
    try {
      await downloadSignalConfig();
    } catch {
      // Silent fail
    }
    setDownloadingSignal(false);
  };

  return (
    <div className="ui-dialog-backdrop is-open" style={{ zIndex: 9999 }}>
      <div
        aria-labelledby="start-modal-title"
        aria-modal="true"
        className="ui-dialog"
        role="dialog"
        style={{ maxWidth: '480px' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <span className="platform-eyebrow">Isolated Range</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: '1.25rem' }}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <h2 id="start-modal-title" style={{ margin: '0 0 0.5rem', fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>
          Connect to the Environment
        </h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.875rem', lineHeight: 1.6, margin: '0 0 1.25rem' }}>
          MIRRAGE runs isolated challenge environments inside Kubernetes. You need an active OpenVPN connection to reach target services.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <button
            type="button"
            onClick={() => { void handleDownloadVpn(); }}
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--radius)',
              cursor: 'pointer',
              textAlign: 'center',
              padding: '1rem',
              color: 'var(--white)',
            }}
          >
            <div style={{ color: 'var(--lime)', marginBottom: '0.5rem', display: 'flex', justifyContent: 'center' }}>
              <Icon name="download" size={24} />
            </div>
            <strong style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>VPN Profile</strong>
            <small style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>
              {downloadingVpn ? 'Downloading...' : 'Get .ovpn profile'}
            </small>
          </button>

          <button
            type="button"
            onClick={() => { void handleDownloadSignal(); }}
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--radius)',
              cursor: 'pointer',
              textAlign: 'center',
              padding: '1rem',
              color: 'var(--white)',
            }}
          >
            <div style={{ color: 'var(--blue, #38bdf8)', marginBottom: '0.5rem', display: 'flex', justifyContent: 'center' }}>
              <Icon name="activity" size={24} />
            </div>
            <strong style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Signal Profile</strong>
            <small style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>
              {downloadingSignal ? 'Downloading...' : 'Get connection metadata'}
            </small>
          </button>
        </div>

        <div className="ui-dialog-actions" style={{ display: 'flex', gap: '0.75rem' }}>
          <Button onClick={onClose} style={{ flex: 1 }} variant="secondary">
            Maybe Later
          </Button>
          <Button onClick={onConfirm} style={{ flex: 1 }} variant="primary" icon="arrow-right">
            Let's Go
          </Button>
        </div>
      </div>
    </div>
  );
}
