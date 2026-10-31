import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  DEMO_EMAIL,
  DEMO_OTP,
  DEMO_PASSWORD,
  mockActivity,
  mockChallenges,
  mockLeaderboard,
  mockSessions,
  mockUser,
  mockVpn,
  type ActivityItem,
  type Challenge,
  type LeaderboardEntry,
  type MockSession,
  type MockUser,
  type MockVpn,
  type SessionStatus,
  type Theme,
  type VpnStatus,
} from '../data/mockData';

type AuthResult = { ok: boolean; message?: string };
type ToastTone = 'success' | 'error' | 'info';

export type Toast = { id: string; title: string; message: string; tone: ToastTone };

type AppContextValue = {
  user: MockUser;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  login: (identifier: string, password: string) => Promise<AuthResult>;
  register: (details: { name: string; username: string; email: string; password: string }) => Promise<AuthResult>;
  requestOtp: (email: string) => Promise<AuthResult>;
  verifyOtp: (code: string) => Promise<AuthResult>;
  logout: () => void;
  resetPassword: (password: string) => Promise<AuthResult>;
  challenges: Challenge[];
  solvedChallengeIds: string[];
  submitFlag: (challengeId: string, flag: string) => Promise<AuthResult & { solved?: boolean }>;
  activities: ActivityItem[];
  sessions: MockSession[];
  startSession: (challengeId: string) => Promise<AuthResult>;
  stopSession: (sessionId: string) => Promise<AuthResult>;
  reconnectSession: (sessionId: string) => Promise<AuthResult>;
  appendTerminalOutput: (sessionId: string, command: string) => void;
  vpn: MockVpn;
  connectVpn: () => Promise<AuthResult>;
  disconnectVpn: () => Promise<AuthResult>;
  simulateVpnError: () => void;
  retryVpn: () => Promise<AuthResult>;
  downloadVpnConfig: () => void;
  leaderboard: LeaderboardEntry[];
  toasts: Toast[];
  pushToast: (title: string, message: string, tone?: ToastTone) => void;
  dismissToast: (id: string) => void;
  updateUser: (details: Pick<MockUser, 'name' | 'username' | 'email'>) => Promise<AuthResult>;
};

const STORAGE_KEY = 'mirrage-demo-state';
const AUTH_KEY = 'mirrage-demo-auth';

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function cloneInitialState() {
  return {
    user: { ...mockUser },
    challenges: mockChallenges.map((challenge) => ({ ...challenge, objectives: [...challenge.objectives], hints: [...challenge.hints], tags: [...challenge.tags] })),
    solvedChallengeIds: [] as string[],
    activities: [...mockActivity],
    sessions: mockSessions.map((session) => ({ ...session, output: [...session.output] })),
    vpn: { ...mockVpn, history: [...mockVpn.history] },
    leaderboard: mockLeaderboard.map((entry) => ({ ...entry })),
  };
}

function readStoredState() {
  const initial = cloneInitialState();
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return initial;
    const parsed = JSON.parse(stored) as Partial<typeof initial>;
    return {
      ...initial,
      ...parsed,
      user: { ...initial.user, ...parsed.user },
      challenges: parsed.challenges ?? initial.challenges,
      activities: parsed.activities ?? initial.activities,
      sessions: parsed.sessions ?? initial.sessions,
      vpn: { ...initial.vpn, ...parsed.vpn },
      leaderboard: parsed.leaderboard ?? initial.leaderboard,
    };
  } catch {
    return initial;
  }
}

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
  const [state, setState] = useState(readStoredState);
  const [isAuthenticated, setIsAuthenticated] = useState(() => window.localStorage.getItem(AUTH_KEY) === 'true');
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [pendingOtpEmail, setPendingOtpEmail] = useState(DEMO_EMAIL);
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setState((current) => {
        let changed = false;
        const now = Date.now();
        const sessions = current.sessions.map((session) => {
          if (session.status === 'starting') {
            changed = true;
            const progress = Math.min(100, session.progress + 20);
            return { ...session, progress, status: progress >= 100 ? 'ready' as SessionStatus : 'starting' as SessionStatus };
          }
          if (session.status === 'ready' && session.expiresAt && session.expiresAt <= now) {
            changed = true;
            return { ...session, status: 'expired' as SessionStatus, expiresAt: null };
          }
          return session;
        });
        return changed ? { ...current, sessions } : current;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const pushToast = useCallback((title: string, message: string, tone: ToastTone = 'info') => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((current) => [...current, { id, title, message, tone }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4200);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const completeAuth = useCallback((email: string, profile?: Partial<MockUser>) => {
    setState((current) => ({ ...current, user: { ...current.user, email, ...profile } }));
    setIsAuthenticated(true);
    window.localStorage.setItem(AUTH_KEY, 'true');
  }, []);

  const login = useCallback(async (identifier: string, password: string): Promise<AuthResult> => {
    setIsAuthLoading(true);
    await delay(700);
    setIsAuthLoading(false);
    if (!identifier.trim() || !password) return { ok: false, message: 'Enter your email or username and password.' };
    if (password !== DEMO_PASSWORD && password !== 'mirrage-demo') return { ok: false, message: 'That password did not match the demo account. Try “observe”.' };
    completeAuth(identifier.includes('@') ? identifier : DEMO_EMAIL, identifier.includes('@') ? {} : { username: identifier });
    return { ok: true };
  }, [completeAuth]);

  const register = useCallback(async (details: { name: string; username: string; email: string; password: string }): Promise<AuthResult> => {
    setIsAuthLoading(true);
    await delay(850);
    setIsAuthLoading(false);
    if (!details.name || !details.username || !details.email || !details.password) return { ok: false, message: 'Complete every required field.' };
    completeAuth(details.email, { name: details.name, username: details.username });
    return { ok: true };
  }, [completeAuth]);

  const requestOtp = useCallback(async (email: string): Promise<AuthResult> => {
    setIsAuthLoading(true);
    await delay(650);
    setIsAuthLoading(false);
    if (!email.includes('@')) return { ok: false, message: 'Enter a valid email address.' };
    setPendingOtpEmail(email);
    return { ok: true, message: 'A simulated code was sent. Use 424242.' };
  }, []);

  const verifyOtp = useCallback(async (code: string): Promise<AuthResult> => {
    setIsAuthLoading(true);
    await delay(650);
    setIsAuthLoading(false);
    if (code !== DEMO_OTP) return { ok: false, message: 'That code is not valid. Use the six-digit demo code 424242.' };
    completeAuth(pendingOtpEmail);
    return { ok: true };
  }, [completeAuth, pendingOtpEmail]);

  const logout = useCallback(() => {
    setIsAuthenticated(false);
    window.localStorage.removeItem(AUTH_KEY);
    pushToast('Signed out', 'Your simulated session has ended.', 'info');
  }, [pushToast]);

  const resetPassword = useCallback(async (password: string): Promise<AuthResult> => {
    setIsAuthLoading(true);
    await delay(700);
    setIsAuthLoading(false);
    if (password.length < 8) return { ok: false, message: 'Use at least 8 characters for the new password.' };
    return { ok: true };
  }, []);

  const submitFlag = useCallback(async (challengeId: string, flag: string): Promise<AuthResult & { solved?: boolean }> => {
    await delay(650);
    const challenge = state.challenges.find((item) => item.id === challengeId);
    if (!challenge) return { ok: false, message: 'Challenge not found.' };
    if (state.solvedChallengeIds.includes(challengeId)) return { ok: true, solved: true, message: 'Already solved — duplicate submissions do not add points.' };
    if (flag.trim() !== challenge.flag) return { ok: false, solved: false, message: 'Incorrect flag. Re-check the signal and try again.' };
    setState((current) => ({
      ...current,
      user: { ...current.user, points: current.user.points + challenge.points },
      solvedChallengeIds: [...current.solvedChallengeIds, challengeId],
      challenges: current.challenges.map((item) => item.id === challengeId ? { ...item, status: 'solved' as const } : item),
      activities: [{ id: `act-${Date.now()}`, type: 'solve', title: 'Challenge solved', detail: `${challenge.title} · +${challenge.points} pts`, timestamp: 'Just now', tone: 'lime' }, ...current.activities],
      leaderboard: current.leaderboard.map((entry) => entry.isCurrentUser ? { ...entry, points: entry.points + challenge.points, solved: entry.solved + 1 } : entry),
    }));
    pushToast('Challenge solved', `You earned ${challenge.points} points from ${challenge.title}.`, 'success');
    return { ok: true, solved: true, message: `Correct. You earned ${challenge.points} points.` };
  }, [pushToast, state.challenges, state.solvedChallengeIds]);

  const startSession = useCallback(async (challengeId: string): Promise<AuthResult> => {
    const challenge = state.challenges.find((item) => item.id === challengeId);
    if (!challenge) return { ok: false, message: 'Choose a valid challenge first.' };
    if (state.sessions.some((session) => ['starting', 'ready'].includes(session.status))) return { ok: false, message: 'You already have an active simulated session.' };
    const session: MockSession = {
      id: `session-${Date.now()}`,
      title: challenge.title,
      target: `${challenge.id}.lab`,
      category: challenge.category,
      status: 'starting',
      ip: `10.42.0.${Math.floor(Math.random() * 80) + 20}`,
      startedAt: 'Just now',
      expiresAt: Date.now() + 30 * 60 * 1000,
      progress: 0,
      output: ['MIRRAGE LAB CONSOLE / SIMULATED', `Provisioning ${challenge.id}.lab...`, 'Allocating isolated network namespace...'],
    };
    setState((current) => ({ ...current, sessions: [session, ...current.sessions], activities: [{ id: `act-${Date.now()}`, type: 'session', title: 'Session provisioning', detail: `${challenge.title} · simulated`, timestamp: 'Just now', tone: 'blue' }, ...current.activities] }));
    pushToast('Session provisioning', 'The isolated lab is starting. This is a simulation.', 'info');
    return { ok: true };
  }, [pushToast, state.challenges, state.sessions]);

  const stopSession = useCallback(async (sessionId: string): Promise<AuthResult> => {
    const found = state.sessions.some((session) => session.id === sessionId && ['starting', 'ready'].includes(session.status));
    if (!found) return { ok: false, message: 'That session is not active.' };
    setState((current) => ({ ...current, sessions: current.sessions.map((session) => session.id === sessionId ? { ...session, status: 'stopping' as const, output: [...session.output, 'Shutdown requested by operator...'] } : session) }));
    await delay(650);
    setState((current) => ({ ...current, sessions: current.sessions.map((session) => session.id === sessionId ? { ...session, status: 'stopped' as const, expiresAt: null, output: [...session.output, 'Environment stopped. Artifacts retained in the activity log.'] } : session) }));
    pushToast('Session stopped', 'The simulated environment has been shut down.', 'info');
    return { ok: true };
  }, [pushToast, state.sessions]);

  const reconnectSession = useCallback(async (sessionId: string): Promise<AuthResult> => {
    const oldSession = state.sessions.find((session) => session.id === sessionId);
    if (!oldSession) return { ok: false, message: 'Session not found.' };
    return startSession(mockChallenges.find((challenge) => challenge.title === oldSession.title)?.id ?? mockChallenges[0].id);
  }, [startSession, state.sessions]);

  const appendTerminalOutput = useCallback((sessionId: string, command: string) => {
    const normalized = command.trim();
    if (!normalized) return;
    const output = normalized === 'help'
      ? 'Available simulated commands: help, status, inspect, clear'
      : normalized === 'status'
        ? 'TARGET STATUS: ready · telemetry: attached · execution: simulated'
        : normalized === 'inspect'
          ? 'TRACE: gateway → proxy → target · hidden signal detected'
          : normalized === 'clear'
            ? ''
            : `simulated@mirrage:~$ ${normalized}\nNo remote command was executed. This console only returns mock output.`;
    setState((current) => ({ ...current, sessions: current.sessions.map((session) => session.id === sessionId ? { ...session, output: output ? [...session.output, `simulated@mirrage:~$ ${normalized}`, output] : [] } : session) }));
  }, []);

  const setVpn = useCallback((status: VpnStatus, details: Partial<MockVpn> = {}) => {
    setState((current) => ({ ...current, vpn: { ...current.vpn, status, ...details } }));
  }, []);

  const connectVpn = useCallback(async (): Promise<AuthResult> => {
    if (state.vpn.status === 'connected') return { ok: false, message: 'VPN is already connected.' };
    setVpn('connecting', { lastError: null });
    await delay(1100);
    setVpn('connected', { ip: '10.42.0.7', connectedAt: Date.now(), lastError: null, history: [{ id: `vpn-${Date.now()}`, event: 'Connected', detail: 'eu-west-02 · simulated', time: 'Just now', tone: 'lime' }, ...state.vpn.history] });
    pushToast('VPN connected', 'The simulated tunnel is ready. No real network connection was made.', 'success');
    return { ok: true };
  }, [pushToast, setVpn, state.vpn.history, state.vpn.status]);

  const disconnectVpn = useCallback(async (): Promise<AuthResult> => {
    if (state.vpn.status === 'disconnected') return { ok: false, message: 'VPN is already disconnected.' };
    await delay(450);
    setVpn('disconnected', { ip: null, connectedAt: null, history: [{ id: `vpn-${Date.now()}`, event: 'Disconnected', detail: 'Manual disconnect · simulated', time: 'Just now', tone: 'muted' }, ...state.vpn.history] });
    pushToast('VPN disconnected', 'The simulated tunnel has been closed.', 'info');
    return { ok: true };
  }, [pushToast, setVpn, state.vpn.history, state.vpn.status]);

  const simulateVpnError = useCallback(() => {
    setVpn('error', { ip: null, connectedAt: null, lastError: 'The simulated gateway did not answer within the test window.' });
    pushToast('VPN connection error', 'Try retrying the simulated connection or review troubleshooting.', 'error');
  }, [pushToast, setVpn]);

  const retryVpn = useCallback(() => connectVpn(), [connectVpn]);

  const downloadVpnConfig = useCallback(() => {
    const content = '# MIRRAGE SIMULATED VPN PROFILE\n# This file is for UI demonstration only.\nserver eu-west-02.mirrage.test\nproto mock\n';
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([content], { type: 'text/plain' }));
    link.download = 'mirrage-simulated-profile.conf';
    link.click();
    URL.revokeObjectURL(link.href);
    pushToast('Mock profile downloaded', 'The file cannot establish a real VPN connection.', 'info');
  }, [pushToast]);

  const updateUser = useCallback(async (details: Pick<MockUser, 'name' | 'username' | 'email'>): Promise<AuthResult> => {
    await delay(650);
    if (!details.name.trim() || !details.username.trim() || !details.email.includes('@')) return { ok: false, message: 'Enter a name, username, and valid email.' };
    setState((current) => ({ ...current, user: { ...current.user, ...details }, activities: [{ id: `act-${Date.now()}`, type: 'profile', title: 'Profile updated', detail: 'Account details saved locally', timestamp: 'Just now', tone: 'lime' }, ...current.activities] }));
    return { ok: true };
  }, []);

  const value = useMemo<AppContextValue>(() => ({
    user: state.user, isAuthenticated, isAuthLoading, login, register, requestOtp, verifyOtp, logout, resetPassword,
    challenges: state.challenges, solvedChallengeIds: state.solvedChallengeIds, submitFlag, activities: state.activities,
    sessions: state.sessions, startSession, stopSession, reconnectSession, appendTerminalOutput, vpn: state.vpn,
    connectVpn, disconnectVpn, simulateVpnError, retryVpn, downloadVpnConfig, leaderboard: state.leaderboard,
    toasts, pushToast, dismissToast, updateUser,
  }), [appendTerminalOutput, connectVpn, dismissToast, downloadVpnConfig, isAuthLoading, isAuthenticated, login, logout, pushToast, reconnectSession, register, requestOtp, resetPassword, retryVpn, simulateVpnError, startSession, state.activities, state.challenges, state.leaderboard, state.sessions, state.solvedChallengeIds, state.user, state.vpn, stopSession, submitFlag, toasts, updateUser, verifyOtp, disconnectVpn]);

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

export const mockCredentials = { email: DEMO_EMAIL, password: DEMO_PASSWORD, otp: DEMO_OTP };
