import { useEffect, useState, useRef, useCallback, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Badge, Button, Card, ProgressBar, StatusBadge } from '../components/ui';
import { EnvironmentLeaveGuardModal } from '../components/EnvironmentLeaveGuardModal';
import { useApp } from '../state/AppState';
import {
  getSessionStatus,
  createSession,
  terminateSession,
  extendSession as apiExtendSession,
  getSlotInfo,
  type SessionStatusResponse,
  type SlotInfo,
} from '../services/sessionService';
import { getVpnStatus, downloadVpnConfig } from '../services/vpnService';

type SessionLifecycleStatus = 'idle' | 'starting' | 'initializing' | 'ready' | 'stopping' | 'failed';
type VpnConnectionStatus = 'unknown' | 'disconnected' | 'connected';

const TOTAL_COUNTDOWN_MS = 3 * 60 * 1000; // 3-minute initialization window

export function SessionsPage() {
  const navigate = useNavigate();
  const { challenges, appendTerminalOutput, pushToast } = useApp();

  // ── Core lifecycle state ──
  const [sessionStatus, setSessionStatus] = useState<SessionLifecycleStatus>('idle');
  const [vpnStatus, setVpnStatus] = useState<VpnConnectionStatus>('unknown');
  const [vpnTunnelIp, setVpnTunnelIp] = useState<string | null>(null);

  // ── 3-minute initialization countdown state ──
  const [initializationDeadline, setInitializationDeadline] = useState<number | null>(null);
  const [timeRemainingMs, setTimeRemainingMs] = useState<number>(TOTAL_COUNTDOWN_MS);
  const [backendReady, setBackendReady] = useState(false);

  // ── Session lifetime countdown & extension state ──
  const [sessionRemainingMs, setSessionRemainingMs] = useState<number>(0);
  const [isExtending, setIsExtending] = useState(false);
  const serverTimeOffsetRef = useRef<number>(0);
  const sessionCountdownIntervalRef = useRef<number | null>(null);

  // ── Session & Cluster metadata ──
  const [sessionData, setSessionData] = useState<SessionStatusResponse | null>(null);
  const [slotInfo, setSlotInfo] = useState<SlotInfo | null>(null);
  const [isCheckingInitial, setIsCheckingInitial] = useState(true);
  const [downloadingVpn, setDownloadingVpn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIp, setCopiedIp] = useState(false);
  const [terminalCommand, setTerminalCommand] = useState('');
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    'MIRRAGE LAB CONSOLE / ACTIVE TELEMETRY',
    'Cluster environment initialized. Ready for observation.',
  ]);

  // ── Leave Guard Navigation Modal ──
  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [pendingNavDestination, setPendingNavDestination] = useState<string | null>(null);
  const [isStoppingFromModal, setIsStoppingFromModal] = useState(false);
  const [modalStopError, setModalStopError] = useState<string | null>(null);

  // ── Timers and Polling Refs ──
  const countdownIntervalRef = useRef<number | null>(null);
  const sessionPollRef = useRef<number | null>(null);
  const vpnPollRef = useRef<number | null>(null);
  const healthPollRef = useRef<number | null>(null);

  const clearCountdown = useCallback(() => {
    if (countdownIntervalRef.current !== null) {
      window.clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  }, []);

  const clearSessionCountdown = useCallback(() => {
    if (sessionCountdownIntervalRef.current !== null) {
      window.clearInterval(sessionCountdownIntervalRef.current);
      sessionCountdownIntervalRef.current = null;
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

  const clearHealthPoll = useCallback(() => {
    if (healthPollRef.current !== null) {
      window.clearInterval(healthPollRef.current);
      healthPollRef.current = null;
    }
  }, []);

  const formatCountdown = (ms: number): string => {
    const totalSecs = Math.max(0, Math.ceil(ms / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const formatSessionCountdown = (ms: number): string => {
    const totalSecs = Math.max(0, Math.floor(ms / 1000));
    const hours = Math.floor(totalSecs / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const updateSessionExpiration = useCallback((res: SessionStatusResponse) => {
    if (!res.expires_at) return;
    const expiresMs = new Date(res.expires_at).getTime();
    if (res.time_remaining_seconds !== undefined) {
      const serverNowMs = expiresMs - res.time_remaining_seconds * 1000;
      serverTimeOffsetRef.current = Date.now() - serverNowMs;
    }
    const currentServerNow = Date.now() - serverTimeOffsetRef.current;
    const remaining = Math.max(0, expiresMs - currentServerNow);
    setSessionRemainingMs(remaining);
  }, []);

  const isEnvironmentActive =
    sessionStatus === 'ready' || sessionStatus === 'initializing' || sessionStatus === 'starting';

  // ── 1. INITIAL SESSION CHECK ──
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
          const isBackendReady = !!statusRes.is_ready && (backendStatus === 'ready' || backendStatus === 'active');
          const isInProgress =
            backendStatus === 'initializing' ||
            backendStatus === 'pending' ||
            backendStatus === 'provisioning';

          if (isBackendReady || isInProgress) {
            setSessionData(statusRes);
            updateSessionExpiration(statusRes);

            const deadlineMs = statusRes.initialization_deadline
              ? new Date(statusRes.initialization_deadline).getTime()
              : statusRes.created_at
              ? new Date(statusRes.created_at).getTime() + TOTAL_COUNTDOWN_MS
              : Date.now();
            const remainingMs = Math.max(0, deadlineMs - Date.now());

            if (remainingMs > 0) {
              setBackendReady(isBackendReady);
              setSessionStatus('initializing');
              setInitializationDeadline(deadlineMs);
              setTimeRemainingMs(remainingMs);
            } else if (isBackendReady) {
              setBackendReady(true);
              setSessionStatus('ready');
            } else {
              setBackendReady(false);
              setSessionStatus('failed');
              setError('Environment did not report ready within the allocated 3-minute window.');
              setInitializationDeadline(null);
              setTimeRemainingMs(0);
            }
            setIsCheckingInitial(false);
            return;
          } else if (backendStatus === 'expired') {
            setError('Your previous session has expired. You can start a new environment.');
          }
        }

        setSessionData(null);
        setBackendReady(false);
        setVpnStatus('unknown');
        setVpnTunnelIp(null);
        setSessionStatus('idle');
      } catch {
        if (mounted) {
          setSessionData(null);
          setBackendReady(false);
          setSessionStatus('idle');
        }
      } finally {
        if (mounted) setIsCheckingInitial(false);
      }
    }

    checkInitialSession();
    return () => {
      mounted = false;
      clearCountdown();
      clearSessionCountdown();
      clearSessionPoll();
      clearVpnPoll();
      clearHealthPoll();
    };
  }, [clearCountdown, clearHealthPoll, clearSessionCountdown, clearSessionPoll, clearVpnPoll, updateSessionExpiration]);

  // ── 2. COUNTDOWN TICKER (INITIALIZATION) ──
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
        if (backendReadyRef.current) {
          setSessionStatus('ready');
        } else {
          setSessionStatus('failed');
          setError('Environment did not report ready within the allocated 3-minute window.');
        }
      }
    };

    tick();
    countdownIntervalRef.current = window.setInterval(tick, 1000);
    return () => {
      clearCountdown();
    };
  }, [sessionStatus, initializationDeadline, clearCountdown]);

  // ── 3. SESSION STATUS POLLING (INITIALIZING) ──
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

        if (res.is_ready && (res.status === 'ready' || res.status === 'active')) {
          setBackendReady(true);
          setSessionData(res);
          if (!initializationDeadline && timeRemainingMs <= 0) {
            clearSessionPoll();
            setSessionStatus('ready');
          }
          return;
        }

        if (res.status === 'error' || res.status === 'terminated' || res.status === 'expired') {
          clearCountdown();
          clearSessionPoll();
          setInitializationDeadline(null);
          setBackendReady(false);
          setSessionData(null);
          setSessionStatus('idle');
          setError(
            res.status === 'terminated'
              ? 'Environment was terminated. The session pod no longer exists.'
              : res.status === 'expired'
              ? 'Session expired. You can start a new environment.'
              : 'The environment encountered an error during provisioning.'
          );
          return;
        }

        setSessionData(res);
      } catch (err: any) {
        if (err.code === '404' || err.status_code === 404) {
          clearCountdown();
          clearSessionPoll();
          setInitializationDeadline(null);
          setBackendReady(false);
          setSessionData(null);
          setSessionStatus('idle');
          setError('Session no longer exists. The environment may have been terminated.');
        }
      }
    };

    poll();
    sessionPollRef.current = window.setInterval(poll, 2500);
    return () => {
      active = false;
      clearSessionPoll();
    };
  }, [sessionStatus, initializationDeadline, timeRemainingMs, clearCountdown, clearSessionPoll]);

  // ── 4. VPN STATUS POLLING (READY) ──
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
        if (active) setVpnStatus('disconnected');
      }
    };

    pollVpn();
    vpnPollRef.current = window.setInterval(pollVpn, 3500);
    return () => {
      active = false;
      clearVpnPoll();
    };
  }, [sessionStatus, clearVpnPoll]);

  // ── 5. SESSION HEALTH POLL (READY) ──
  useEffect(() => {
    if (sessionStatus !== 'ready') {
      clearHealthPoll();
      return;
    }

    let active = true;
    const checkHealth = async () => {
      try {
        const res = await getSessionStatus();
        if (!active) return;

        if (res.status === 'terminated' || res.status === 'expired' || res.status === 'error' || !res.is_ready) {
          clearHealthPoll();
          clearVpnPoll();
          clearSessionCountdown();
          setBackendReady(false);
          setSessionData(null);
          setVpnStatus('unknown');
          setVpnTunnelIp(null);
          setSessionStatus('idle');
          setError('Environment has ended. You can launch a fresh pod.');
        } else {
          setSessionData(res);
          updateSessionExpiration(res);
        }
      } catch {
        // Transient network error
      }
    };

    healthPollRef.current = window.setInterval(checkHealth, 10000);
    return () => {
      active = false;
      clearHealthPoll();
    };
  }, [sessionStatus, clearHealthPoll, clearVpnPoll, clearSessionCountdown, updateSessionExpiration]);

  // ── 6. NAVIGATION GUARDS & BEFOREUNLOAD ──
  useEffect(() => {
    if (!isEnvironmentActive) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isEnvironmentActive]);

  useEffect(() => {
    if (!isEnvironmentActive) return;
    window.history.pushState(null, '', window.location.href);
    const handlePopState = () => {
      window.history.pushState(null, '', window.location.href);
      setPendingNavDestination('/dashboard');
      setModalStopError(null);
      setShowLeaveModal(true);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isEnvironmentActive]);

  // ── 7. SESSION EXPIRATION COUNTDOWN TICKER ──
  useEffect(() => {
    if (!isEnvironmentActive || !sessionData?.expires_at) {
      clearSessionCountdown();
      return;
    }

    const tickSession = async () => {
      if (!sessionData?.expires_at) return;
      const expiresMs = new Date(sessionData.expires_at).getTime();
      const currentServerNow = Date.now() - serverTimeOffsetRef.current;
      const remaining = Math.max(0, expiresMs - currentServerNow);
      setSessionRemainingMs(remaining);

      if (remaining <= 0) {
        clearSessionCountdown();
        setSessionStatus('idle');
        setSessionData(null);
        setError('Environment expired. You can start a new environment.');
      }
    };

    tickSession();
    sessionCountdownIntervalRef.current = window.setInterval(tickSession, 1000);
    return () => clearSessionCountdown();
  }, [isEnvironmentActive, sessionData?.expires_at, clearSessionCountdown]);

  // ── HANDLERS ──
  const handleStartEnvironment = async () => {
    if (sessionStatus !== 'idle' && sessionStatus !== 'failed') return;
    setError(null);
    setBackendReady(false);
    setSessionStatus('starting');

    try {
      const res = await createSession();
      setSessionData(res as SessionStatusResponse);
      updateSessionExpiration(res as SessionStatusResponse);
      if (res.status === 'ready') setBackendReady(true);
      setSessionStatus('initializing');

      const deadline = res.initialization_deadline
        ? new Date(res.initialization_deadline).getTime()
        : Date.now() + TOTAL_COUNTDOWN_MS;
      setInitializationDeadline(deadline);
      const remaining = Math.max(0, deadline - Date.now());
      setTimeRemainingMs(remaining > 0 ? remaining : TOTAL_COUNTDOWN_MS);
      pushToast('Pod initializing', 'Preparing your private CTF environment.', 'info');
    } catch (err: any) {
      setError(err.message || 'Failed to start environment. Cluster may be at capacity.');
      setSessionStatus('failed');
    }
  };

  const handleStopEnvironment = async () => {
    if (sessionStatus === 'stopping') return;
    const previousStatus = sessionStatus;
    setSessionStatus('stopping');
    clearCountdown();
    clearSessionCountdown();
    clearSessionPoll();
    clearVpnPoll();
    clearHealthPoll();
    setInitializationDeadline(null);

    try {
      await terminateSession(sessionData?.session_id);
      setSessionStatus('idle');
      setSessionData(null);
      setBackendReady(false);
      setVpnStatus('unknown');
      setVpnTunnelIp(null);
      setSessionRemainingMs(0);
      setError(null);
      const slots = await getSlotInfo().catch(() => null);
      if (slots) setSlotInfo(slots);
      pushToast('Environment terminated', 'Pod deleted and slot released.', 'info');
    } catch (err: any) {
      setError(err.message || 'Failed to stop environment.');
      setSessionStatus(previousStatus);
    }
  };

  const handleExtendSession = async () => {
    if (isExtending || !isEnvironmentActive) return;
    setIsExtending(true);
    try {
      const res = await apiExtendSession(sessionData?.session_id);
      setSessionData(res);
      updateSessionExpiration(res);
      pushToast('Session extended', '+1 hour added to session lifespan.', 'success');
    } catch (err: any) {
      setError(err.message || 'Failed to extend session.');
    } finally {
      setIsExtending(false);
    }
  };

  const handleDownloadVpn = async () => {
    setDownloadingVpn(true);
    try {
      const filename = sessionData?.session_id
        ? `mirrage-${sessionData.session_id.substring(0, 8)}.ovpn`
        : 'mirrage.ovpn';
      await downloadVpnConfig(filename);
    } catch (err: any) {
      setError(err.message || 'Failed to download VPN profile.');
    } finally {
      setDownloadingVpn(false);
    }
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIp(true);
      setTimeout(() => setCopiedIp(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleNavClick = (e: React.MouseEvent, destination: string) => {
    if (isEnvironmentActive) {
      e.preventDefault();
      setPendingNavDestination(destination);
      setModalStopError(null);
      setShowLeaveModal(true);
    } else {
      navigate(destination);
    }
  };

  const handleModalStay = () => {
    setShowLeaveModal(false);
    setPendingNavDestination(null);
  };

  const handleModalStopAndLeave = async () => {
    setIsStoppingFromModal(true);
    setModalStopError(null);
    clearCountdown();
    clearSessionCountdown();
    clearSessionPoll();
    clearVpnPoll();
    clearHealthPoll();

    try {
      await terminateSession(sessionData?.session_id);
      setSessionStatus('idle');
      setSessionData(null);
      setShowLeaveModal(false);
      const target = pendingNavDestination || '/dashboard';
      setPendingNavDestination(null);
      navigate(target);
    } catch (err: any) {
      setModalStopError(err.message || 'Failed to stop environment.');
    } finally {
      setIsStoppingFromModal(false);
    }
  };

  const handleTerminalCommand = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const cmd = terminalCommand.trim();
    if (!cmd) return;
    appendTerminalOutput('active', cmd);
    setTerminalLogs((prev) => [
      ...prev,
      `operator@mirrage:~$ ${cmd}`,
      cmd === 'status'
        ? `POD: ${sessionStatus} · IP: ${sessionData?.mirage_ip || '10.42.0.x'} · VPN: ${vpnStatus}`
        : cmd === 'help'
        ? 'Available commands: help, status, targets, clear'
        : cmd === 'targets'
        ? `TARGET SUBNET: 10.42.0.0/16 · CHALLENGES: ${challenges.map((c) => c.slug).join(', ')}`
        : `Command sent to telemetry logging daemon.`,
    ]);
    setTerminalCommand('');
  };

  const mirageIp = sessionData?.mirage_ip || null;
  const ctfUrl = mirageIp ? `http://${mirageIp}:80` : null;
  const countdownComplete = timeRemainingMs <= 0 && !initializationDeadline;

  return (
    <div className="platform-page sessions-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">03 / isolated environments</span>
          <h1>Session Console</h1>
          <p>Start and manage your private CTF machine.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <Button onClick={(e) => handleNavClick(e, '/challenges')} size="small" variant="ghost" icon="terminal">
            Challenges
          </Button>
          <Button onClick={(e) => handleNavClick(e, '/vpn')} size="small" variant="ghost" icon="vpn">
            VPN
          </Button>
          {slotInfo && (
            <Badge tone={slotInfo.available_slots > 0 ? 'lime' : 'red'} dot>
              {slotInfo.active_slots} / {slotInfo.total_slots} Slots Active
            </Badge>
          )}
          <Badge tone={sessionStatus === 'ready' ? 'lime' : sessionStatus === 'initializing' ? 'orange' : 'muted'} dot>
            {sessionStatus === 'ready' ? 'Pod Live' : sessionStatus === 'initializing' ? 'Provisioning' : 'Console Idle'}
          </Badge>
        </div>
      </div>

      {error && (
        <div className="auth-alert auth-alert-error" style={{ marginBottom: '1.5rem' }}>
          <Icon name="info" size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* ── STATE 1: IDLE / STOPPED ── */}
      {sessionStatus === 'idle' && (
        <Card style={{ padding: '2rem', textAlign: 'center', maxWidth: '640px', margin: '1rem auto' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: 'var(--panel-deep)', color: 'var(--lime)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem' }}>
            <Icon name="server" size={24} />
          </div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', margin: '0 0 0.5rem' }}>
            Deploy Isolated Machine
          </h2>
          <p style={{ color: 'var(--muted)', fontSize: '0.875rem', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto 1.5rem' }}>
            Start your environment to receive a target address. Connect through OpenVPN, explore the machine, and capture the flags.
          </p>

          <Button
            disabled={isCheckingInitial || (slotInfo ? slotInfo.available_slots <= 0 : false)}
            icon="play"
            loading={isCheckingInitial}
            onClick={handleStartEnvironment}
            size="large"
            style={{ minWidth: '220px' }}
            variant="primary"
          >
            Start Environment
          </Button>
        </Card>
      )}

      {/* ── STATE 2: STARTING / INITIALIZING (3-Minute Countdown) ── */}
      {(sessionStatus === 'starting' || sessionStatus === 'initializing') && (
        <Card style={{ padding: '2.5rem', textAlign: 'center', maxWidth: '600px', margin: '1rem auto' }}>
          <span className="platform-eyebrow" style={{ color: 'var(--lime)', marginBottom: '0.5rem', display: 'block' }}>
            {sessionStatus === 'starting' ? 'Allocating Pod' : 'Initializing Environment'}
          </span>

          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '3.5rem', fontWeight: 700, letterSpacing: '0.1em', margin: '0.5rem 0', color: 'var(--white)' }}>
            {formatCountdown(timeRemainingMs)}
          </div>

          <div style={{ maxWidth: '320px', margin: '1rem auto 1.5rem' }}>
            <ProgressBar
              label="Initialization sequence"
              tone="blue"
              value={Math.min(100, Math.max(0, ((TOTAL_COUNTDOWN_MS - timeRemainingMs) / TOTAL_COUNTDOWN_MS) * 100))}
            />
          </div>

          <p style={{ color: 'var(--muted)', fontSize: '0.8125rem', lineHeight: 1.6, margin: '0 0 1.5rem' }}>
            {backendReady
              ? '✓ Kubernetes infrastructure ready. Completing mandatory network stabilization sequence...'
              : countdownComplete
              ? 'Waiting for container ports to report ready...'
              : 'Container provisioning in progress. Target endpoints will unlock when initialization completes.'}
          </p>

          <Button onClick={handleStopEnvironment} size="small" variant="ghost">
            Cancel and Stop
          </Button>
        </Card>
      )}

      {/* ── STATE 3: READY (Active Machine, Endpoints & Controls) ── */}
      {sessionStatus === 'ready' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {/* Lifespan & Timer Card */}
          <Card style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span className="platform-card-kicker">Session Lifetime</span>
              <Badge tone={sessionRemainingMs <= 10 * 60 * 1000 ? 'red' : 'lime'}>
                {sessionRemainingMs <= 10 * 60 * 1000 ? 'Expiring Soon' : 'Active'}
              </Badge>
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '2.5rem', fontWeight: 700, color: sessionRemainingMs <= 10 * 60 * 1000 ? 'var(--red, #ef4444)' : 'var(--white)', margin: '0.5rem 0' }}>
              {formatSessionCountdown(sessionRemainingMs)}
            </div>
            <p style={{ color: 'var(--muted)', fontSize: '0.75rem', margin: '0 0 1rem' }}>
              Inactivity timeout enforced. Auto-terminates when counter expires.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Button
                disabled={isExtending}
                icon="plus"
                loading={isExtending}
                onClick={handleExtendSession}
                size="small"
                variant="secondary"
              >
                + Add 1 Hour
              </Button>
              <Button
                icon="stop"
                onClick={handleStopEnvironment}
                size="small"
                variant="danger"
              >
                Stop Machine
              </Button>
            </div>
          </Card>

          {/* Target Endpoints Card */}
          <Card style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span className="platform-card-kicker">Target Gateway</span>
              <Badge tone="blue">Subnet 10.42.0.0/16</Badge>
            </div>
            <div style={{ margin: '0.75rem 0' }}>
              <strong style={{ display: 'block', fontSize: '1.25rem', fontFamily: 'var(--font-mono)', color: 'var(--white)' }}>
                {mirageIp || '10.42.0.x'}
              </strong>
              <small style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>Port 80 (HTTP) · Port 22 (SSH)</small>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {ctfUrl && (
                <Button
                  icon="external"
                  onClick={() => handleCopy(ctfUrl)}
                  size="small"
                  variant="secondary"
                >
                  {copiedIp ? 'Copied!' : 'Copy URL'}
                </Button>
              )}
              <Button
                icon="download"
                loading={downloadingVpn}
                onClick={handleDownloadVpn}
                size="small"
                variant="primary"
              >
                Get .ovpn
              </Button>
            </div>
          </Card>

          {/* VPN Telemetry Card */}
          <Card style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span className="platform-card-kicker">OpenVPN Telemetry</span>
              <StatusBadge status={vpnStatus === 'connected' ? 'Connected' : 'Disconnected'} />
            </div>
            <div style={{ margin: '0.75rem 0' }}>
              <strong style={{ display: 'block', fontSize: '1.25rem', fontFamily: 'var(--font-mono)', color: 'var(--white)' }}>
                {vpnTunnelIp || 'Not Attached'}
              </strong>
              <small style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>Assigned Client Tunnel Address</small>
            </div>
            <p style={{ color: 'var(--muted)', fontSize: '0.75rem', margin: 0 }}>
              {vpnStatus === 'connected'
                ? 'Routing active. You can reach the pod IP directly through your OpenVPN client.'
                : 'Connect your OpenVPN client using your profile to establish network access.'}
            </p>
          </Card>

          {/* Interactive Shell / Terminal */}
          <Card padding="none" style={{ gridColumn: '1 / -1', overflow: 'hidden' }}>
            <div className="terminal-panel" style={{ margin: 0, borderRadius: 0 }}>
              <div className="terminal-header">
                <span><i /> <i /> <i /></span>
                <span>operator@mirrage:~ (live pod session)</span>
                <Badge tone="lime">Connected</Badge>
              </div>
              <div className="terminal-output" style={{ minHeight: '180px', maxHeight: '260px' }}>
                {terminalLogs.map((line, idx) => (
                  <div key={idx} className={idx === 0 ? 'terminal-muted' : ''}>
                    <span className="terminal-prompt">{idx > 0 ? '›' : '#'}</span>
                    {line}
                  </div>
                ))}
              </div>
              <form className="terminal-command" onSubmit={handleTerminalCommand}>
                <span>operator@mirrage:~$</span>
                <input
                  autoComplete="off"
                  onChange={(e) => setTerminalCommand(e.target.value)}
                  placeholder="type status, targets, or help"
                  value={terminalCommand}
                />
                <button aria-label="Send command" type="submit">
                  <Icon name="send" size={15} />
                </button>
              </form>
            </div>
          </Card>
        </div>
      )}

      {/* Navigation Leave Guard Modal */}
      <EnvironmentLeaveGuardModal
        isOpen={showLeaveModal}
        isStopping={isStoppingFromModal}
        onStay={handleModalStay}
        onStopAndLeave={handleModalStopAndLeave}
        stopError={modalStopError}
      />
    </div>
  );
}
