import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { MirrageLogo } from '../components/MirrageLogo';
import {
  createSession,
  getSessionStatus,
  terminateSession,
  getSlotInfo,
  type SessionStatusResponse,
  type SessionResponse,
  type SlotInfo,
} from '../services/sessionService';
import { getVpnStatus, downloadVpnConfig } from '../services/vpnService';

type SessionLifecycleStatus = 'idle' | 'starting' | 'initializing' | 'ready' | 'stopping' | 'failed';
type VpnConnectionStatus = 'unknown' | 'disconnected' | 'connected';

const TOTAL_COUNTDOWN_MS = 3 * 60 * 1000; // 3-minute mandatory initialization window

export function SessionPage() {
  // ── Core lifecycle state ──
  const [sessionStatus, setSessionStatus] = useState<SessionLifecycleStatus>('idle');
  const [vpnStatus, setVpnStatus] = useState<VpnConnectionStatus>('unknown');

  // ── Mandatory 3-minute countdown ──
  // The deadline is the absolute timestamp when the initialization window ends.
  // This is the sole source of truth for the frontend timer.
  const [initializationDeadline, setInitializationDeadline] = useState<number | null>(null);
  const [timeRemainingMs, setTimeRemainingMs] = useState<number>(TOTAL_COUNTDOWN_MS);

  // ── Backend readiness (tracked SEPARATELY from UI lifecycle) ──
  // The pod/infrastructure may become ready long before the 3-minute window ends.
  // This flag records that fact WITHOUT transitioning the UI to 'ready'.
  const [backendReady, setBackendReady] = useState(false);

  // ── Session metadata ──
  const [sessionData, setSessionData] = useState<SessionStatusResponse | SessionResponse | null>(null);
  const [slotInfo, setSlotInfo] = useState<SlotInfo | null>(null);
  const [vpnTunnelIp, setVpnTunnelIp] = useState<string | null>(null);

  // ── Action & feedback states ──
  const [isCheckingInitial, setIsCheckingInitial] = useState(true);
  const [downloadingVpn, setDownloadingVpn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIp, setCopiedIp] = useState(false);

  // ── Interval timer refs for reliable cleanup ──
  const countdownIntervalRef = useRef<number | null>(null);
  const sessionPollRef = useRef<number | null>(null);
  const vpnPollRef = useRef<number | null>(null);

  const clearCountdown = useCallback(() => {
    if (countdownIntervalRef.current !== null) {
      window.clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  }, []);

  const clearSessionPoll = useCallback(() => {
    if (sessionPollRef.current !== null) {
      window.clearInterval(sessionPollRef.current);
      sessionPollRef.current = null;
    }
  }, []);

  const clearVpnPoll = useCallback(() => {
    if (vpnPollRef.current !== null) {
      window.clearInterval(vpnPollRef.current);
      vpnPollRef.current = null;
    }
  }, []);

  // Format milliseconds into MM:SS
  const formatCountdown = (ms: number): string => {
    const totalSecs = Math.max(0, Math.ceil(ms / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // ════════════════════════════════════════════════════════════════════
  // 1. INITIAL PAGE LOAD — detect existing session on refresh
  // ════════════════════════════════════════════════════════════════════
  useEffect(() => {
    let mounted = true;

    async function checkInitialSession() {
      setIsCheckingInitial(true);
      try {
        const [statusRes, slotsRes] = await Promise.all([
          getSessionStatus().catch(() => null),
          getSlotInfo().catch(() => null),
        ]);

        if (!mounted) return;
        if (slotsRes) setSlotInfo(slotsRes);

        if (statusRes) {
          const backendStatus = statusRes.status;
          const isBackendReady = statusRes.is_ready || backendStatus === 'ready' || backendStatus === 'active';
          const isInProgress =
            backendStatus === 'initializing' ||
            backendStatus === 'pending' ||
            backendStatus === 'provisioning';

          if (isBackendReady || isInProgress) {
            setSessionData(statusRes);

            // Calculate how much of the mandatory 3-minute window remains
            const createdAtMs = statusRes.created_at
              ? new Date(statusRes.created_at).getTime()
              : Date.now();
            const elapsedMs = Math.max(0, Date.now() - createdAtMs);
            const remainingMs = Math.max(0, TOTAL_COUNTDOWN_MS - elapsedMs);

            if (remainingMs > 0) {
              // 3-minute window still active — show initializing with reconstructed countdown
              setBackendReady(isBackendReady);
              setSessionStatus('initializing');
              setInitializationDeadline(Date.now() + remainingMs);
              setTimeRemainingMs(remainingMs);
            } else if (isBackendReady) {
              // 3-minute window has passed AND backend is ready — go straight to ready
              setBackendReady(true);
              setSessionStatus('ready');
            } else {
              // 3 minutes exceeded but backend still not ready
              setBackendReady(false);
              setSessionStatus('initializing');
              // Keep polling with 0 remaining — the UI will show "still initializing"
              setInitializationDeadline(null);
              setTimeRemainingMs(0);
            }
            setIsCheckingInitial(false);
            return;
          }
        }

        // No active session found
        setSessionStatus('idle');
        setIsCheckingInitial(false);
      } catch {
        if (mounted) {
          setSessionStatus('idle');
          setIsCheckingInitial(false);
        }
      }
    }

    checkInitialSession();

    return () => {
      mounted = false;
      clearCountdown();
      clearSessionPoll();
      clearVpnPoll();
    };
  }, [clearCountdown, clearSessionPoll, clearVpnPoll]);

  // ════════════════════════════════════════════════════════════════════
  // 2. COUNTDOWN TICK — absolute-deadline-based, ticks every second
  // ════════════════════════════════════════════════════════════════════
  //
  // The backendReadyRef lets the tick callback read the latest backendReady
  // without adding it to the effect dependency array (which would restart the interval).
  const backendReadyRef = useRef(backendReady);
  useEffect(() => {
    backendReadyRef.current = backendReady;
  }, [backendReady]);

  useEffect(() => {
    if (sessionStatus !== 'initializing' || !initializationDeadline) {
      clearCountdown();
      return;
    }

    const tick = () => {
      const remaining = Math.max(0, initializationDeadline - Date.now());
      setTimeRemainingMs(remaining);

      if (remaining <= 0) {
        clearCountdown();
        setInitializationDeadline(null);

        // Countdown complete — check if backend is also ready
        if (backendReadyRef.current) {
          // BOTH conditions met: countdown done AND backend ready → show READY
          setSessionStatus('ready');
        }
        // If backend NOT ready yet, stay in 'initializing' with timeRemainingMs=0.
        // The polling effect continues and will transition to ready once backend confirms.
      }
    };

    tick();
    countdownIntervalRef.current = window.setInterval(tick, 1000);

    return () => {
      clearCountdown();
    };
  }, [sessionStatus, initializationDeadline, clearCountdown]);

  // ════════════════════════════════════════════════════════════════════
  // 3. SESSION STATUS POLLING — runs during 'initializing'
  // ════════════════════════════════════════════════════════════════════
  //
  // When backend reports READY:
  //   - Set backendReady = true
  //   - Do NOT change sessionStatus to 'ready'
  //   - The countdown or post-countdown logic handles that transition
  //
  // When backend reports ERROR/TERMINATED/EXPIRED:
  //   - Immediately abort → show error
  useEffect(() => {
    if (sessionStatus !== 'initializing') {
      clearSessionPoll();
      return;
    }

    let active = true;

    const poll = async () => {
      try {
        const res = await getSessionStatus();
        if (!active) return;

        if (res.is_ready || res.status === 'ready' || res.status === 'active') {
          // Backend is ready — record this, but do NOT skip the countdown
          setBackendReady(true);
          setSessionData(res);

          // If countdown has already finished (timeRemainingMs reached 0 and
          // initializationDeadline was cleared), transition to ready now
          if (!initializationDeadline && timeRemainingMs <= 0) {
            clearSessionPoll();
            setSessionStatus('ready');
          }
          // Otherwise: countdown is still running, stay in 'initializing'
          return;
        }

        if (res.status === 'error' || res.status === 'terminated' || res.status === 'expired') {
          clearCountdown();
          clearSessionPoll();
          setInitializationDeadline(null);
          setBackendReady(false);
          setSessionStatus('failed');
          setError('The environment encountered an error during provisioning.');
          return;
        }

        // Still initializing — update session data for metadata
        setSessionData(res);
      } catch {
        // Transient network error — keep polling
      }
    };

    // Immediate first poll, then every 2.5s
    poll();
    sessionPollRef.current = window.setInterval(poll, 2500);

    return () => {
      active = false;
      clearSessionPoll();
    };
  }, [sessionStatus, initializationDeadline, timeRemainingMs, clearCountdown, clearSessionPoll]);

  // ════════════════════════════════════════════════════════════════════
  // 4. VPN STATUS POLLING — only when UI is in READY state
  // ════════════════════════════════════════════════════════════════════
  useEffect(() => {
    if (sessionStatus !== 'ready') {
      clearVpnPoll();
      return;
    }

    let active = true;

    const pollVpn = async () => {
      try {
        const vpn = await getVpnStatus();
        if (!active) return;
        setVpnStatus(vpn.is_connected ? 'connected' : 'disconnected');
        setVpnTunnelIp(vpn.assigned_ip || null);
      } catch {
        if (active) {
          setVpnStatus('disconnected');
        }
      }
    };

    pollVpn();
    vpnPollRef.current = window.setInterval(pollVpn, 3500);

    return () => {
      active = false;
      clearVpnPoll();
    };
  }, [sessionStatus, clearVpnPoll]);

  // ════════════════════════════════════════════════════════════════════
  // HANDLER: Start Environment (explicit user click only)
  // ════════════════════════════════════════════════════════════════════
  const handleStartEnvironment = async () => {
    // Only allow starting from idle or failed — prevent double session creation
    if (sessionStatus !== 'idle' && sessionStatus !== 'failed') {
      return;
    }

    setError(null);
    setBackendReady(false);
    setSessionStatus('starting');

    try {
      const res = await createSession();
      setSessionData(res);

      // ALWAYS enter the mandatory 3-minute initialization window.
      // Even if the backend immediately reports 'ready', the UI must show
      // the full countdown. Backend readiness is tracked separately.
      if (res.status === 'ready') {
        setBackendReady(true);
      }
      setSessionStatus('initializing');
      const deadline = Date.now() + TOTAL_COUNTDOWN_MS;
      setInitializationDeadline(deadline);
      setTimeRemainingMs(TOTAL_COUNTDOWN_MS);
    } catch (err: unknown) {
      const apiErr = err as { message?: string; detail?: string };
      const msg =
        apiErr.detail || apiErr.message || 'Failed to start environment. Please try again.';
      setError(msg);
      setSessionStatus('failed');
    }
  };

  // ════════════════════════════════════════════════════════════════════
  // HANDLER: Stop Environment
  // ════════════════════════════════════════════════════════════════════
  const handleStopEnvironment = async () => {
    if (sessionStatus === 'stopping') return; // Guard against double-click

    const previousStatus = sessionStatus;
    setSessionStatus('stopping');
    clearCountdown();
    clearSessionPoll();
    clearVpnPoll();
    setInitializationDeadline(null);

    try {
      await terminateSession();
      setSessionStatus('idle');
      setSessionData(null);
      setBackendReady(false);
      setVpnStatus('unknown');
      setVpnTunnelIp(null);
      setError(null);

      const slots = await getSlotInfo().catch(() => null);
      if (slots) setSlotInfo(slots);
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      setError(apiErr.message || 'Failed to stop environment.');
      // Do not falsely show stopped — restore previous state
      setSessionStatus(previousStatus);
    }
  };

  // ════════════════════════════════════════════════════════════════════
  // HANDLER: Download VPN Profile (explicit user click only — NO auto-download)
  // ════════════════════════════════════════════════════════════════════
  const handleDownloadVpn = async () => {
    setDownloadingVpn(true);
    try {
      const filename = sessionData?.session_id
        ? `mirrage-${sessionData.session_id.substring(0, 8)}.ovpn`
        : 'mirrage.ovpn';
      await downloadVpnConfig(filename);
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      setError(apiErr.message || 'Failed to download VPN profile.');
    } finally {
      setDownloadingVpn(false);
    }
  };

  // ════════════════════════════════════════════════════════════════════
  // HANDLER: Manual status check (from error/timeout state)
  // ════════════════════════════════════════════════════════════════════
  const handleCheckStatus = async () => {
    setError(null);
    try {
      const res = await getSessionStatus();
      setSessionData(res);
      const isReady = res.is_ready || res.status === 'ready' || res.status === 'active';

      if (isReady) {
        // Backend is ready — check if 3-minute window has passed
        const createdAtMs = res.created_at ? new Date(res.created_at).getTime() : 0;
        const elapsedMs = Date.now() - createdAtMs;

        if (elapsedMs >= TOTAL_COUNTDOWN_MS) {
          setBackendReady(true);
          setSessionStatus('ready');
        } else {
          // Still within the 3-minute window — show remaining countdown
          const remainingMs = Math.max(0, TOTAL_COUNTDOWN_MS - elapsedMs);
          setBackendReady(true);
          setSessionStatus('initializing');
          setInitializationDeadline(Date.now() + remainingMs);
          setTimeRemainingMs(remainingMs);
        }
      } else if (
        res.status === 'initializing' ||
        res.status === 'pending' ||
        res.status === 'provisioning'
      ) {
        setBackendReady(false);
        setSessionStatus('initializing');
        const deadline = Date.now() + 60000; // Give an extra minute
        setInitializationDeadline(deadline);
        setTimeRemainingMs(60000);
      } else {
        setSessionStatus('idle');
      }
    } catch {
      setError('Could not reach active session. You can start a new environment.');
      setSessionStatus('idle');
    }
  };

  const handleCopyIp = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIp(true);
      setTimeout(() => setCopiedIp(false), 2000);
    } catch {
      // Fallback
    }
  };

  const mirageIp = sessionData?.mirage_ip || '10.42.0.17';
  const miragePort = sessionData?.mirage_port || 22;

  // Whether the countdown has reached zero
  const countdownComplete = timeRemainingMs <= 0 && !initializationDeadline;

  return (
    <div className="min-h-screen bg-[var(--bg)] flex">
      {/* Main Console Content */}
      <div className="flex-1 flex flex-col justify-center px-6 sm:px-12 max-w-xl mx-auto py-12">
        <div className="flex items-center justify-between mb-10">
          <MirrageLogo size="lg" />
          <Link
            to="/dashboard"
            className="text-xs font-mono text-[var(--text-faint)] hover:text-[var(--text)] transition-colors"
          >
            ← Return to Dashboard
          </Link>
        </div>

        <h1 className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--accent)] mb-2">
          {sessionStatus === 'ready'
            ? 'MIRRAGE ACTIVE TARGET'
            : sessionStatus === 'initializing'
            ? 'ENVIRONMENT INITIALIZING'
            : sessionStatus === 'stopping'
            ? 'ENVIRONMENT STOPPING'
            : 'ENVIRONMENT CONSOLE'}
        </h1>

        <p className="text-sm text-[var(--text-muted)] mb-8 leading-relaxed">
          {sessionStatus === 'ready'
            ? 'Your isolated honeypot and target container are listening on the challenge subnet.'
            : sessionStatus === 'initializing'
            ? 'Provisioning dedicated dual-container pod. Target endpoints will unlock once ready.'
            : sessionStatus === 'stopping'
            ? 'Tearing down your environment and releasing resources.'
            : 'Launch your private, isolated training machine inside the MIRRAGE cluster.'}
        </p>

        {/* Initial Loading Indicator */}
        {isCheckingInitial && (
          <div className="p-8 text-center bg-[var(--surface)] border border-[var(--border)] rounded">
            <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="font-mono text-xs text-[var(--text-muted)] animate-pulse-subtle">
              Checking environment status...
            </p>
          </div>
        )}

        {/* ─── STATE 1: IDLE / STOPPED (Start Button) ─── */}
        {!isCheckingInitial && sessionStatus === 'idle' && (
          <div className="space-y-6">
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-6">
              <h2 className="font-serif text-lg text-[var(--text)] mb-2">
                Deploy Isolated Environment
              </h2>
              <p className="text-xs text-[var(--text-muted)] mb-6 leading-relaxed">
                Clicking start allocates a dual-container pod (Mirage Decoy + CTF Target).
                Environment initialization takes up to 3 minutes.
              </p>

              {slotInfo && (
                <div className="mb-6 p-3 bg-[var(--surface-alt)] rounded border border-[var(--border)] flex justify-between items-center text-xs font-mono">
                  <span className="text-[var(--text-muted)]">Cluster Capacity</span>
                  <span
                    className={
                      slotInfo.available_slots > 0
                        ? 'text-[var(--success)]'
                        : 'text-[var(--danger)]'
                    }
                  >
                    {slotInfo.active_slots} / {slotInfo.total_slots} active slots
                  </span>
                </div>
              )}

              <button
                onClick={handleStartEnvironment}
                disabled={slotInfo ? slotInfo.available_slots <= 0 : false}
                className="btn-primary w-full py-3.5 text-xs font-mono uppercase tracking-widest flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                Start Environment
              </button>
            </div>
          </div>
        )}

        {/* ─── STATE 2: STARTING (In-Flight POST) ─── */}
        {!isCheckingInitial && sessionStatus === 'starting' && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-8 text-center">
            <div className="w-6 h-6 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <button
              disabled
              className="btn-primary w-full py-3.5 text-xs font-mono uppercase tracking-widest opacity-80 cursor-not-allowed mb-3"
            >
              Starting...
            </button>
            <p className="text-xs text-[var(--text-muted)] font-mono animate-pulse-subtle">
              Allocating environment slot with orchestrator...
            </p>
          </div>
        )}

        {/* ─── STATE 3: INITIALIZING (Mandatory 3-Minute Countdown) ─── */}
        {!isCheckingInitial && sessionStatus === 'initializing' && (
          <div className="space-y-6">
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-8 text-center">
              <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--accent)] block mb-3">
                Initializing Environment
              </span>

              {/* ── THE VISIBLE MM:SS COUNTDOWN ── */}
              <div className="font-mono text-5xl sm:text-6xl tracking-widest text-[var(--text)] font-semibold mb-4">
                {formatCountdown(timeRemainingMs)}
              </div>

              {/* Secondary progress bar synced to actual countdown */}
              <div className="h-1 bg-[var(--surface-alt)] rounded-full overflow-hidden max-w-xs mx-auto mb-4">
                <div
                  className="h-full bg-[var(--accent)] transition-all duration-1000 ease-linear"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(0, ((TOTAL_COUNTDOWN_MS - timeRemainingMs) / TOTAL_COUNTDOWN_MS) * 100)
                    )}%`,
                  }}
                />
              </div>

              {/* Status message depends on whether countdown is done but backend not ready */}
              <p className="text-xs text-[var(--text-muted)] leading-relaxed max-w-sm mx-auto">
                {countdownComplete && !backendReady
                  ? 'Environment is still initializing. Waiting for backend to report ready...'
                  : 'Your MIRRAGE environment is being prepared. You can stop the environment at any time.'}
              </p>

              {/* Show a subtle indicator if backend became ready early */}
              {backendReady && !countdownComplete && (
                <p className="text-[11px] text-[var(--success)] font-mono mt-3">
                  ✓ Infrastructure ready — completing initialization
                </p>
              )}
            </div>

            <div className="text-center">
              <button
                onClick={handleStopEnvironment}
                className="text-xs font-mono text-[var(--text-faint)] hover:text-[var(--danger)] transition-colors cursor-pointer"
              >
                Stop Environment
              </button>
            </div>
          </div>
        )}

        {/* ─── STATE 4: READY (VPN Instructions & Profile Download) ─── */}
        {!isCheckingInitial && sessionStatus === 'ready' && (
          <div className="space-y-6 animate-fade-in">
            {/* Target Gateway Card */}
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
                  TARGET GATEWAY
                </span>
                <span className="font-mono text-[11px] text-[var(--accent)] bg-[var(--accent-subtle)] px-2 py-0.5 rounded">
                  SSH Port {miragePort}
                </span>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="font-mono text-xl sm:text-2xl text-[var(--text)] tracking-wider">
                  {mirageIp}
                </span>
                <button
                  onClick={() => handleCopyIp(`${mirageIp}`)}
                  className="text-xs font-mono text-[var(--text-muted)] hover:text-[var(--text)] transition-colors px-2 py-1 rounded bg-[var(--surface-alt)] cursor-pointer"
                  title="Copy IP"
                >
                  {copiedIp ? 'Copied!' : 'Copy IP'}
                </button>
              </div>
              <p className="text-[11px] text-[var(--text-faint)] mt-2 font-mono">
                ssh -p {miragePort} mirrage@{mirageIp}
              </p>
            </div>

            {/* VPN Connection Instructions & Explicit Download */}
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-6">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--success)] inline-block"></span>
                <h2 className="font-serif text-lg text-[var(--text)] font-semibold">
                  Environment Ready
                </h2>
              </div>
              <p className="text-xs text-[var(--text-muted)] mb-5 leading-relaxed">
                To connect to your MIRRAGE environment, download the VPN profile and import it into
                your OpenVPN client.
              </p>

              {/* 4 Concise Steps */}
              <div className="space-y-2.5 mb-6 bg-[var(--surface-alt)] p-4 rounded border border-[var(--border)]/60">
                <div className="flex items-start gap-3 text-xs text-[var(--text)]">
                  <span className="font-mono text-[var(--accent)] font-bold">1.</span>
                  <span>Download the VPN profile below.</span>
                </div>
                <div className="flex items-start gap-3 text-xs text-[var(--text)]">
                  <span className="font-mono text-[var(--accent)] font-bold">2.</span>
                  <span>
                    Open it with your OpenVPN client (OpenVPN Connect, Tunnelblick, or openvpn CLI).
                  </span>
                </div>
                <div className="flex items-start gap-3 text-xs text-[var(--text)]">
                  <span className="font-mono text-[var(--accent)] font-bold">3.</span>
                  <span>Connect to the VPN.</span>
                </div>
                <div className="flex items-start gap-3 text-xs text-[var(--text)]">
                  <span className="font-mono text-[var(--accent)] font-bold">4.</span>
                  <span>Return here to access your environment.</span>
                </div>
              </div>

              {/* Download VPN Profile Button (Explicit user click only — NO auto-download) */}
              <button
                onClick={handleDownloadVpn}
                disabled={downloadingVpn}
                className="btn-primary w-full py-3.5 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 cursor-pointer"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                {downloadingVpn ? 'Downloading Profile...' : 'Download VPN Profile'}
              </button>
            </div>

            {/* VPN Status Telemetry */}
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
                  VPN Status
                </span>
                <div className="flex items-center gap-2">
                  {vpnStatus === 'connected' ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-[var(--success)] inline-block"></span>
                      <span className="font-mono text-xs text-[var(--success)] font-medium">
                        Connected
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full border border-[var(--text-faint)] inline-block"></span>
                      <span className="font-mono text-xs text-[var(--text-muted)]">
                        Disconnected
                      </span>
                    </>
                  )}
                </div>
              </div>
              {vpnTunnelIp && (
                <div className="flex justify-between text-xs font-mono pt-2 border-t border-[var(--border)]">
                  <span className="text-[var(--text-muted)]">Tunnel IP</span>
                  <span className="text-[var(--text)]">{vpnTunnelIp}</span>
                </div>
              )}
            </div>

            {/* Action Bar */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Link
                to="/challenges"
                className="btn-primary flex-1 text-center py-2.5 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-1"
              >
                Go to Challenges <span>→</span>
              </Link>
              <button
                onClick={handleStopEnvironment}
                className="btn-outline py-2.5 px-4 text-xs font-mono uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--danger)] hover:border-[var(--danger)]/50 transition-colors cursor-pointer"
              >
                Stop Environment
              </button>
            </div>
          </div>
        )}

        {/* ─── STATE: STOPPING (Teardown In-Flight) ─── */}
        {!isCheckingInitial && sessionStatus === 'stopping' && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-8 text-center">
            <div className="w-6 h-6 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="font-mono text-xs uppercase tracking-wider text-[var(--text-muted)] mb-3">
              Stopping Environment
            </p>
            <p className="text-xs text-[var(--text-faint)] font-mono">
              Tearing down pod and releasing slot...
            </p>
            <div className="flex gap-3 mt-6">
              <button
                disabled
                className="btn-primary flex-1 py-2.5 text-xs font-mono uppercase tracking-wider opacity-50 cursor-not-allowed"
              >
                Start Environment
              </button>
              <button
                disabled
                className="btn-outline flex-1 py-2.5 text-xs font-mono uppercase tracking-wider opacity-50 cursor-not-allowed"
              >
                Stopping...
              </button>
            </div>
          </div>
        )}

        {/* ─── STATE 5: FAILED / TIMEOUT ─── */}
        {!isCheckingInitial && sessionStatus === 'failed' && (
          <div className="bg-[var(--surface)] border border-[var(--danger)]/30 rounded p-6">
            <div className="flex items-center gap-2 mb-2 text-[var(--danger)]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span className="font-mono text-xs uppercase tracking-wider font-semibold">
                Environment Notice
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-5 leading-relaxed">
              {error || 'Environment did not report ready within the allocated window.'}
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleStartEnvironment}
                className="btn-primary flex-1 py-2 text-xs font-mono uppercase tracking-wider cursor-pointer"
              >
                Try Again
              </button>
              <button
                onClick={handleCheckStatus}
                className="btn-outline flex-1 py-2 text-xs font-mono uppercase tracking-wider cursor-pointer"
              >
                Check Status
              </button>
            </div>
          </div>
        )}

        {/* Global Error Notice if any */}
        {error && sessionStatus !== 'failed' && (
          <div className="mt-4 p-3 bg-[var(--danger-subtle)] border border-[var(--danger)]/20 rounded text-xs text-[var(--danger)]">
            {error}
          </div>
        )}
      </div>

      {/* Right Decorative Panel */}
      <div className="hidden lg:flex flex-col justify-end items-end p-12 w-64 border-l border-[var(--border)]/40">
        <p className="font-mono text-[11px] text-right text-[var(--text-faint)] leading-relaxed tracking-wider mb-4">
          {sessionData?.session_id && (
            <span className="block text-[var(--text-muted)] mb-2 text-[10px]">
              SESSION ID<br />
              <span className="text-[var(--accent)] font-semibold">
                {sessionData.session_id.substring(0, 8)}
              </span>
            </span>
          )}
        </p>
        <p className="font-serif text-sm text-[var(--text-faint)] italic text-right leading-relaxed">
          "What you see<br />is not what was built."
        </p>
      </div>
    </div>
  );
}
