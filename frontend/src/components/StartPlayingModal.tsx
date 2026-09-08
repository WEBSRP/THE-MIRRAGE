import { useState } from 'react';
import { downloadVpnConfig, downloadSignalConfig } from '../services/vpnService';

/**
 * StartPlayingModal — "Want to try this?" modal (reference screen 05).
 * Shows VPN and Signal download options before entering the environment.
 */
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
      // Silent fail — VPN might not be configured yet
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-[var(--surface)] border border-[var(--border)] rounded w-full max-w-md mx-4 p-6 animate-fade-in">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[var(--text-faint)] hover:text-[var(--text)] transition-colors cursor-pointer text-lg"
          aria-label="Close"
        >
          ×
        </button>

        {/* Content */}
        <h2 className="font-serif text-xl text-[var(--text)] mb-2">Want to try this?</h2>
        <p className="text-[var(--text-muted)] text-sm mb-6 leading-relaxed">
          MIRRAGE runs in an isolated environment. You'll need a VPN connection to enter the challenge network.
        </p>

        {/* Download cards */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {/* VPN Card */}
          <button
            onClick={handleDownloadVpn}
            disabled={downloadingVpn}
            className="bg-[var(--surface-alt)] border border-[var(--border)] rounded p-4 text-center hover:border-[var(--accent)]/30 transition-colors cursor-pointer group"
          >
            <div className="flex justify-center mb-2">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--accent)]">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </div>
            <p className="text-[var(--text)] text-sm font-medium">Download VPN</p>
            <p className="text-[var(--text-faint)] text-[11px] mt-0.5">
              {downloadingVpn ? 'Downloading...' : 'Get your OpenVPN profile'}
            </p>
          </button>

          {/* Signal Card */}
          <button
            onClick={handleDownloadSignal}
            disabled={downloadingSignal}
            className="bg-[var(--surface-alt)] border border-[var(--border)] rounded p-4 text-center hover:border-[var(--accent)]/30 transition-colors cursor-pointer group"
          >
            <div className="flex justify-center mb-2">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--accent)]">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </div>
            <p className="text-[var(--text)] text-sm font-medium">Download Signal</p>
            <p className="text-[var(--text-faint)] text-[11px] mt-0.5">
              {downloadingSignal ? 'Downloading...' : 'Get announcements and updates'}
            </p>
          </button>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            Let's Go <span>→</span>
          </button>
          <button
            onClick={onClose}
            className="btn-outline flex-1"
          >
            Maybe Later
          </button>
        </div>
      </div>
    </div>
  );
}
