import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  type ActivityItem,
  type Challenge as UIChallenge,
  type Difficulty,
  type LeaderboardEntry,
  type MockSession,
  type MockUser,
  type MockVpn,
  type SessionStatus,
  type Theme,
} from '../data/mockData';
import {
  getMe,
  logout as apiLogout,
  requestOtp as apiRequestOtp,
  verifyOtp as apiVerifyOtp,
  resendOtp as apiResendOtp,
  getToken,
  type User as ApiUser,
} from '../services/authService';
import {
  getChallenges as apiGetChallenges,
  submitFlag as apiSubmitFlag,
  type Challenge as ApiChallenge,
} from '../services/challengeService';
import {
  createSession as apiCreateSession,
  getSessionStatus as apiGetSessionStatus,
  terminateSession as apiTerminateSession,
  extendSession as apiExtendSession,
  getSlotInfo as apiGetSlotInfo,
  type SessionStatusResponse,
  type SessionResponse,
  type SlotInfo,
} from '../services/sessionService';
import {
  getVpnStatus as apiGetVpnStatus,
  downloadVpnConfig as apiDownloadVpnConfig,
  downloadSignalConfig as apiDownloadSignalConfig,
  type VpnStatus as ApiVpnStatus,
} from '../services/vpnService';
import {
  getActivity as apiGetActivity,
  type ActivityLog,
} from '../services/activityService';

export type AuthResult = { ok: boolean; message?: string };
export type ToastTone = 'success' | 'error' | 'info';
export type Toast = { id: string; title: string; message: string; tone: ToastTone };

export interface ExtendedChallenge extends UIChallenge {
  slug: string;
  backendId?: string;
  is_solved?: boolean;
}

export type AppContextValue = {
  user: MockUser & Partial<ApiUser>;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  resendOtp: (email: string) => Promise<AuthResult>;
  requestOtp: (email: string) => Promise<AuthResult>;
  verifyOtp: (code: string, email?: string) => Promise<AuthResult>;
  logout: () => void;
  challenges: ExtendedChallenge[];
  solvedChallengeIds: string[];
  refreshChallenges: () => Promise<void>;
  submitFlag: (challengeSlugOrId: string, flag: string) => Promise<AuthResult & { solved?: boolean }>;
  activities: ActivityItem[];
  refreshActivities: () => Promise<void>;
  sessions: MockSession[];
  activeSessionData: SessionStatusResponse | SessionResponse | null;
  slotInfo: SlotInfo | null;
  startSession: (challengeSlugOrId?: string) => Promise<AuthResult>;
  stopSession: (sessionId?: string) => Promise<AuthResult>;
  extendSession: (sessionId?: string) => Promise<AuthResult>;
  reconnectSession: (sessionId?: string) => Promise<AuthResult>;
  appendTerminalOutput: (sessionId: string, command: string) => void;
  vpn: MockVpn;
  vpnTelemetry: ApiVpnStatus | null;
  refreshVpnStatus: () => Promise<void>;
  connectVpn: () => Promise<AuthResult>;
  disconnectVpn: () => Promise<AuthResult>;
  simulateVpnError: () => void;
  retryVpn: () => Promise<AuthResult>;
  downloadVpnConfig: (filename?: string | unknown) => Promise<void>;
  downloadSignalConfig: () => Promise<void>;
  leaderboard: LeaderboardEntry[];
  toasts: Toast[];
  pushToast: (title: string, message: string, tone?: ToastTone) => void;
  dismissToast: (id: string) => void;
  updateUser: (details: Pick<MockUser, 'name' | 'username' | 'email'>) => Promise<AuthResult>;
};

const getDifficulty = (points: number): Difficulty => {
  if (points <= 100) return 'Easy';
  if (points <= 250) return 'Medium';
  if (points <= 500) return 'Hard';
  return 'Expert';
};

const EVENT_LABEL_MAP: Record<string, string | null> = {
  session_start: 'Environment started',
  session_stop: 'Environment stopped',
  vpn_connect: 'VPN connected',
  vpn_disconnect: 'VPN disconnected',
  flag_submission: 'Flag submitted',
  ssh_auth_attempt: null,
  ssh_command: null,
  honeypot_trigger: null,
  deception_discovery: null,
};

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin} min ago`;

  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();
  if (isToday) return `Today · ${timeStr}`;

  if (diffHours < 168) {
    const weekday = date.toLocaleDateString([], { weekday: 'short' });
    return `${weekday} · ${timeStr}`;
  }
  return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} · ${timeStr}`;
}

const defaultUser: MockUser & Partial<ApiUser> = {
  name: 'Operator',
  username: 'operator',
  email: '',
  role: 'Operator',
  avatar: 'O',
  points: 0,
  rank: 1,
  createdAt: new Date().toISOString(),
  id: '',
  is_active: true,
  is_admin: false,
};

const AppContext = createContext<AppContextValue | null>(null);
const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void; setTheme: (theme: Theme) => void } | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => window.localStorage.getItem('mirrage-theme') === 'light' ? 'light' : 'dark');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem('mirrage-theme', theme);
  }, [theme]);
  const value = useMemo(() => ({ theme, setTheme, toggleTheme: () => setTheme((current) => current === 'dark' ? 'light' : 'dark') }), [theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MockUser & Partial<ApiUser>>(defaultUser);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => getToken() !== null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [pendingOtpEmail, setPendingOtpEmail] = useState('');
  const [toasts, setToasts] = useState<Toast[]>([]);

  const [challenges, setChallenges] = useState<ExtendedChallenge[]>([]);
  const [solvedChallengeIds, setSolvedChallengeIds] = useState<string[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [activeSessionData, setActiveSessionData] = useState<SessionStatusResponse | SessionResponse | null>(null);
  const [slotInfo, setSlotInfo] = useState<SlotInfo | null>(null);
  const [vpnTelemetry, setVpnTelemetry] = useState<ApiVpnStatus | null>(null);
  const [terminalOutput, setTerminalOutput] = useState<string[]>(['MIRRAGE LAB CONSOLE', 'Connected to observation layer']);

  const pushToast = useCallback((title: string, message: string, tone: ToastTone = 'info') => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((current) => [...current, { id, title, message, tone }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4200);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const mapApiUserToMockUser = useCallback((apiUser: ApiUser, currentPoints = 0): MockUser & ApiUser => {
    return {
      ...apiUser,
      name: apiUser.username,
      username: apiUser.username,
      email: apiUser.email,
      role: apiUser.is_admin ? 'Admin' : 'Operator',
      avatar: (apiUser.username.charAt(0) || 'O').toUpperCase(),
      points: currentPoints,
      rank: 1,
      createdAt: apiUser.created_at,
    };
  }, []);

  // ── Refresh Challenges from Real API ──
  const refreshChallenges = useCallback(async () => {
    if (!getToken()) return;
    try {
      const data = await apiGetChallenges();
      const list: ApiChallenge[] = Array.isArray(data) ? data : (data as any)?.challenges || [];
      const solvedIds: string[] = [];
      let totalEarnedPoints = 0;

      const mapped: ExtendedChallenge[] = list.map((ch) => {
        const diff = getDifficulty(ch.points);
        if (ch.is_solved) {
          solvedIds.push(ch.slug);
          solvedIds.push(ch.id);
          totalEarnedPoints += ch.points;
        }
        return {
          id: ch.slug,
          slug: ch.slug,
          backendId: ch.id,
          title: ch.title,
          category: ch.category,
          difficulty: diff,
          points: ch.points,
          estimatedTime: ch.points <= 100 ? '20 min' : ch.points <= 250 ? '45 min' : '60 min',
          solveRate: 40,
          description: ch.description,
          objectives: [
            'Establish an active connection through the private OpenVPN tunnel.',
            'Investigate listening targets on the assigned pod subnet.',
            'Recover and submit the flag to record your findings.',
          ],
          hints: ch.hint ? [ch.hint] : ['Inspect routing tables and listening services.'],
          tags: [ch.category, diff],
          flag: '',
          status: ch.is_solved ? 'solved' : 'available',
          is_solved: ch.is_solved,
        };
      });

      setChallenges(mapped);
      setSolvedChallengeIds(solvedIds);
      setUser((current) => ({ ...current, points: totalEarnedPoints }));
    } catch {
      // Not logged in or network error
    }
  }, []);

  // ── Refresh Activities from Real API ──
  const refreshActivities = useCallback(async () => {
    if (!getToken()) return;
    try {
      const raw = await apiGetActivity(20, 0);
      const list: ActivityLog[] = Array.isArray(raw) ? raw : (raw as any)?.activities || (raw as any)?.items || [];
      const mapped: ActivityItem[] = [];
      for (const item of list) {
        const label = EVENT_LABEL_MAP[item.event_type];
        if (label === null) continue;
        const displayTitle = label ?? (item.summary || item.event_type);
        mapped.push({
          id: item.id,
          type: item.event_type.includes('session') ? 'session' : item.event_type.includes('vpn') ? 'vpn' : 'profile',
          title: displayTitle,
          detail: item.source_ip ? `Source IP: ${item.source_ip}` : 'Platform event recorded',
          timestamp: formatRelativeTime(item.timestamp),
          tone: item.event_type.includes('flag') ? 'lime' : item.event_type.includes('stop') ? 'muted' : 'blue',
        });
      }
      setActivities(mapped);
    } catch {
      // Handled silently
    }
  }, []);

  // ── Refresh VPN Status from Real API ──
  const refreshVpnStatus = useCallback(async () => {
    if (!getToken()) return;
    try {
      const status = await apiGetVpnStatus();
      setVpnTelemetry(status);
    } catch {
      // Offline / not connected
    }
  }, []);

  // ── Refresh Session Status & Slots from Real API ──
  const refreshSessionStatus = useCallback(async () => {
    if (!getToken()) return;
    try {
      const [statusRes, slotsRes] = await Promise.all([
        apiGetSessionStatus().catch(() => null),
        apiGetSlotInfo().catch(() => null),
      ]);
      if (slotsRes) setSlotInfo(slotsRes);
      if (statusRes) {
        setActiveSessionData(statusRes);
      } else {
        setActiveSessionData(null);
      }
    } catch {
      // Ignored
    }
  }, []);

  // ── INITIAL USER LOAD on mount ──
  useEffect(() => {
    let mounted = true;
    async function initUser() {
      const token = getToken();
      if (!token) {
        if (mounted) {
          setIsAuthenticated(false);
          setIsAuthLoading(false);
        }
        return;
      }
      try {
        const me = await getMe();
        if (mounted) {
          setUser(mapApiUserToMockUser(me));
          setIsAuthenticated(true);
        }
      } catch {
        apiLogout();
        if (mounted) {
          setUser(defaultUser);
          setIsAuthenticated(false);
        }
      } finally {
        if (mounted) {
          setIsAuthLoading(false);
        }
      }
    }

    initUser();
    return () => {
      mounted = false;
    };
  }, [mapApiUserToMockUser]);

  // When user is authenticated, load initial data
  useEffect(() => {
    if (isAuthenticated) {
      refreshChallenges();
      refreshActivities();
      refreshVpnStatus();
      refreshSessionStatus();
    }
  }, [isAuthenticated, refreshChallenges, refreshActivities, refreshVpnStatus, refreshSessionStatus]);

  // Periodic polling for VPN and Session while authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    const interval = window.setInterval(() => {
      refreshVpnStatus();
      refreshSessionStatus();
    }, 6000);
    return () => window.clearInterval(interval);
  }, [isAuthenticated, refreshVpnStatus, refreshSessionStatus]);

  // ── AUTH HANDLERS ──
  const requestOtp = useCallback(async (email: string): Promise<AuthResult> => {
    setIsAuthLoading(true);
    try {
      const res = await apiRequestOtp(email);
      setPendingOtpEmail(email);
      return { ok: true, message: res.message || 'Verification code sent to your email.' };
    } catch (err: any) {
      return { ok: false, message: err.message || 'Unable to send verification code.' };
    } finally {
      setIsAuthLoading(false);
    }
  }, []);

  const verifyOtp = useCallback(async (code: string, emailParam?: string): Promise<AuthResult> => {
    const emailToUse = emailParam || pendingOtpEmail;
    if (!emailToUse) return { ok: false, message: 'No email found for OTP verification.' };
    setIsAuthLoading(true);
    try {
      const res = await apiVerifyOtp(emailToUse, code);
      setUser(mapApiUserToMockUser(res.user));
      setIsAuthenticated(true);
      pushToast('Authentication successful', `Signed in as ${res.user.username}`, 'success');
      return { ok: true };
    } catch (err: any) {
      return { ok: false, message: err.message || 'Invalid verification code.' };
    } finally {
      setIsAuthLoading(false);
    }
  }, [mapApiUserToMockUser, pendingOtpEmail, pushToast]);

  const logout = useCallback(() => {
    apiLogout();
    setUser(defaultUser);
    setIsAuthenticated(false);
    setActiveSessionData(null);
    pushToast('Signed out', 'Your MIRRAGE session has ended.', 'info');
  }, [pushToast]);

  const resendOtp = useCallback(async (email: string): Promise<AuthResult> => {
    setIsAuthLoading(true);
    try {
      const res = await apiResendOtp(email);
      return { ok: true, message: res.message };
    } catch (err: any) {
      return { ok: false, message: err.message || "Unable to resend verification code." };
    } finally {
      setIsAuthLoading(false);
    }
  }, []);

  // ── CTF FLAG SUBMISSION ──
  const submitFlag = useCallback(async (challengeSlugOrId: string, flag: string): Promise<AuthResult & { solved?: boolean }> => {
    const ch = challenges.find((c) => c.slug === challengeSlugOrId || c.id === challengeSlugOrId || c.backendId === challengeSlugOrId);
    const targetSlug = ch?.slug || challengeSlugOrId;

    try {
      const res = await apiSubmitFlag({ challenge_slug: targetSlug, flag: flag.trim() });
      if (res.is_correct) {
        setSolvedChallengeIds((current) => [...current, targetSlug]);
        setChallenges((current) =>
          current.map((item) =>
            item.slug === targetSlug || item.id === targetSlug
              ? { ...item, status: 'solved', is_solved: true }
              : item
          )
        );
        setUser((current) => ({
          ...current,
          points: current.points + res.points_awarded,
        }));
        pushToast('Flag accepted', res.message || `+${res.points_awarded} points awarded!`, 'success');
        refreshActivities();
        return { ok: true, solved: true, message: res.message };
      } else {
        return { ok: false, solved: false, message: res.message || 'Incorrect flag.' };
      }
    } catch (err: any) {
      return { ok: false, solved: false, message: err.message || 'Failed to submit flag.' };
    }
  }, [challenges, pushToast, refreshActivities]);

  // ── SESSION MANAGEMENT (K8S PODS) ──
  const startSession = useCallback(async (_challengeSlugOrId?: string): Promise<AuthResult> => {
    try {
      const res = await apiCreateSession();
      setActiveSessionData(res);
      pushToast('Environment requested', 'Kubernetes pod is provisioning. Initializing endpoints...', 'info');
      refreshSessionStatus();
      refreshActivities();
      return { ok: true };
    } catch (err: any) {
      const msg = err.message || 'Failed to start environment. The cluster may be at capacity.';
      pushToast('Environment error', msg, 'error');
      return { ok: false, message: msg };
    }
  }, [pushToast, refreshActivities, refreshSessionStatus]);

  const stopSession = useCallback(async (sessionId?: string): Promise<AuthResult> => {
    try {
      const idToStop = sessionId || (activeSessionData as SessionStatusResponse)?.session_id;
      const res = await apiTerminateSession(idToStop);
      setActiveSessionData(res);
      pushToast('Environment stopped', 'Pod deleted and cluster slot released.', 'info');
      refreshSessionStatus();
      refreshActivities();
      return { ok: true };
    } catch (err: any) {
      const msg = err.message || 'Failed to stop environment.';
      pushToast('Stop error', msg, 'error');
      return { ok: false, message: msg };
    }
  }, [activeSessionData, pushToast, refreshActivities, refreshSessionStatus]);

  const extendSession = useCallback(async (sessionId?: string): Promise<AuthResult> => {
    try {
      const idToExtend = sessionId || (activeSessionData as SessionStatusResponse)?.session_id;
      const res = await apiExtendSession(idToExtend);
      setActiveSessionData(res);
      pushToast('Session extended', 'Added 1 hour to your environment lifecycle.', 'success');
      return { ok: true };
    } catch (err: any) {
      const msg = err.message || 'Unable to extend session.';
      pushToast('Extension error', msg, 'error');
      return { ok: false, message: msg };
    }
  }, [activeSessionData, pushToast]);

  const reconnectSession = useCallback(async (sessionId?: string): Promise<AuthResult> => {
    return startSession(sessionId);
  }, [startSession]);

  const appendTerminalOutput = useCallback((_sessionId: string, command: string) => {
    const normalized = command.trim();
    if (!normalized) return;
    const output =
      normalized === 'help'
        ? 'Available commands: help, status, targets, vpn, clear'
        : normalized === 'status'
        ? `POD STATUS: ${activeSessionData?.status || 'idle'} · TARGET IP: ${activeSessionData?.mirage_ip || 'none'}`
        : normalized === 'targets'
        ? `ACTIVE TARGETS: ${challenges.map((c) => c.slug).join(', ')}`
        : normalized === 'vpn'
        ? `VPN TUNNEL: ${vpnTelemetry?.is_connected ? `Connected (${vpnTelemetry.assigned_ip})` : 'Disconnected'}`
        : normalized === 'clear'
        ? ''
        : `operator@mirrage:~$ ${normalized}\nCommand executed on observation layer.`;

    setTerminalOutput((prev) => (output ? [...prev, `operator@mirrage:~$ ${normalized}`, output] : []));
  }, [activeSessionData, challenges, vpnTelemetry]);

  const downloadVpnConfig = useCallback(async (filename?: string | unknown) => {
    try {
      const fname = typeof filename === 'string' ? filename : undefined;
      await apiDownloadVpnConfig(fname);
      pushToast('VPN profile downloaded', 'Import your .ovpn profile into OpenVPN Connect or CLI.', 'success');
    } catch (err: any) {
      pushToast('Download failed', err.message || 'Unable to retrieve VPN profile.', 'error');
    }
  }, [pushToast]);

  const downloadSignalConfig = useCallback(async () => {
    try {
      await apiDownloadSignalConfig();
      pushToast('Signal profile downloaded', 'Connection metadata profile ready.', 'success');
    } catch (err: any) {
      pushToast('Download failed', err.message || 'Unable to retrieve Signal profile.', 'error');
    }
  }, [pushToast]);

  const connectVpn = useCallback(async (): Promise<AuthResult> => {
    await refreshVpnStatus();
    if (vpnTelemetry?.is_connected) {
      return { ok: true, message: 'VPN is connected.' };
    }
    pushToast('OpenVPN Notice', 'Connect your OpenVPN client using your downloaded profile to establish the tunnel.', 'info');
    return { ok: true };
  }, [pushToast, refreshVpnStatus, vpnTelemetry?.is_connected]);

  const disconnectVpn = useCallback(async (): Promise<AuthResult> => {
    pushToast('OpenVPN Notice', 'Disconnect directly in your OpenVPN client to close the tunnel.', 'info');
    return { ok: true };
  }, [pushToast]);

  const simulateVpnError = useCallback(() => {
    pushToast('VPN Check', 'OpenVPN client is not currently reporting an active connection.', 'info');
  }, [pushToast]);

  const retryVpn = useCallback(() => refreshVpnStatus().then(() => ({ ok: true })), [refreshVpnStatus]);

  const updateUser = useCallback(async (details: Pick<MockUser, 'name' | 'username' | 'email'>): Promise<AuthResult> => {
    setUser((current) => ({ ...current, ...details }));
    pushToast('Profile updated', 'Your display settings have been saved.', 'success');
    return { ok: true };
  }, [pushToast]);

  // Derive mock-compatible UI session representations from real activeSessionData
  const sessions: MockSession[] = useMemo(() => {
    if (!activeSessionData) {
      return [
        {
          id: 'session-main',
          title: challenges[0]?.title || 'Main Environment',
          target: challenges[0]?.slug || 'lab-target',
          category: challenges[0]?.category || 'Perception',
          status: 'stopped' as SessionStatus,
          ip: '10.42.0.x',
          startedAt: 'Idle',
          expiresAt: null,
          progress: 0,
          output: terminalOutput,
        },
      ];
    }

    const s = activeSessionData;
    const statusMap: Record<string, SessionStatus> = {
      ready: 'ready',
      active: 'ready',
      initializing: 'starting',
      pending: 'starting',
      provisioning: 'starting',
      stopping: 'stopping',
      terminated: 'stopped',
      expired: 'expired',
      error: 'error',
    };
    const mappedStatus = statusMap[s.status] || 'ready';

    return [
      {
        id: s.session_id || 'session-active',
        title: challenges[0]?.title || 'CTF Environment',
        target: `${s.mirage_ip || '10.42.0.x'}:80`,
        category: 'Isolated Lab',
        status: mappedStatus,
        ip: s.mirage_ip || '10.42.0.x',
        startedAt: 'Active',
        expiresAt: s.expires_at ? new Date(s.expires_at).getTime() : null,
        progress: mappedStatus === 'ready' ? 100 : 50,
        output: terminalOutput,
      },
    ];
  }, [activeSessionData, challenges, terminalOutput]);

  // Derive mock-compatible UI VPN state from real vpnTelemetry
  const vpn: MockVpn = useMemo(() => {
    const isConn = Boolean(vpnTelemetry?.is_connected);
    return {
      status: isConn ? 'connected' : 'disconnected',
      server: 'themirrage.me:1194',
      ip: vpnTelemetry?.assigned_ip || null,
      connectedAt: vpnTelemetry?.connected_since ? new Date(vpnTelemetry.connected_since).getTime() : null,
      lastError: null,
      history: [
        {
          id: 'vpn-telemetry-1',
          event: isConn ? 'Connected' : 'Disconnected',
          detail: vpnTelemetry?.assigned_ip ? `Assigned IP ${vpnTelemetry.assigned_ip}` : 'No active tunnel session',
          time: 'Live',
          tone: isConn ? 'lime' : 'muted',
        },
      ],
    };
  }, [vpnTelemetry]);

  // Leaderboard data
  const leaderboard: LeaderboardEntry[] = useMemo(() => {
    return [
      { rank: 1, name: user.name, username: user.username, points: user.points, solved: solvedChallengeIds.length, change: 0, isCurrentUser: true },
      { rank: 2, name: 'CipherZero', username: 'cipherzero', points: 450, solved: 2, change: 1, isCurrentUser: false },
      { rank: 3, name: 'HexDrifter', username: 'hexdrifter', points: 300, solved: 1, change: -1, isCurrentUser: false },
    ];
  }, [solvedChallengeIds.length, user.name, user.points, user.username]);

  const value = useMemo<AppContextValue>(() => ({
    user,
    isAuthenticated,
    isAuthLoading,
    requestOtp,
    resendOtp,
    verifyOtp,
    logout,
    challenges,
    solvedChallengeIds,
    refreshChallenges,
    submitFlag,
    activities,
    refreshActivities,
    sessions,
    activeSessionData,
    slotInfo,
    startSession,
    stopSession,
    extendSession,
    reconnectSession,
    appendTerminalOutput,
    vpn,
    vpnTelemetry,
    refreshVpnStatus,
    connectVpn,
    disconnectVpn,
    simulateVpnError,
    retryVpn,
    downloadVpnConfig,
    downloadSignalConfig,
    leaderboard,
    toasts,
    pushToast,
    dismissToast,
    updateUser,
  }), [
    user,
    isAuthenticated,
    isAuthLoading,
    requestOtp,
    resendOtp,
    verifyOtp,
    logout,
    challenges,
    solvedChallengeIds,
    refreshChallenges,
    submitFlag,
    activities,
    refreshActivities,
    sessions,
    activeSessionData,
    slotInfo,
    startSession,
    stopSession,
    extendSession,
    reconnectSession,
    appendTerminalOutput,
    vpn,
    vpnTelemetry,
    refreshVpnStatus,
    connectVpn,
    disconnectVpn,
    simulateVpnError,
    retryVpn,
    downloadVpnConfig,
    downloadSignalConfig,
    leaderboard,
    toasts,
    pushToast,
    dismissToast,
    updateUser,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used inside AppProvider');
  return context;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used inside ThemeProvider');
  return context;
}
