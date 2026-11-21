import { useCallback, useEffect, useRef, useState } from 'react';
import { canDownloadSessionVpn } from './services/sessionService';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Button, Modal, ToastViewport } from './components/ui';
import { AvailabilityNotice } from './components/AvailabilityNotice';
import { AuthLayout, PlatformLayout } from './layouts/PlatformLayout';
import { LandingPage } from './pages/LandingPage';
import { ChallengeDetailPage, ChallengesPage } from './pages/ChallengesPages';
import { LoginPage, VerifyOtpPage } from './pages/AuthPages';
import { DashboardPage } from './pages/DashboardPage';
import { VpnPage } from './pages/VpnPage';
import { SessionsPage } from './pages/SessionsPage';
import { ProfilePage, SettingsPage } from './pages/AccountPages';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { DocsPage } from './pages/DocsPage';
import { useApp } from './state/AppState';

function SessionReadyNotice() {
  const { activeSessionData, isAuthenticated, pushToast } = useApp();
  const navigate = useNavigate();
  const announced = useRef<string | null>(null);
  const [noticeSession, setNoticeSession] = useState<string | null>(null);
  const sessionId = isAuthenticated && canDownloadSessionVpn(activeSessionData)
    ? activeSessionData?.session_id
    : undefined;
  const close = useCallback(() => setNoticeSession(null), []);

  useEffect(() => {
    if (!sessionId || announced.current === sessionId) return;
    const key = 'mirrage-vpn-ready-notice';
    try {
      if (sessionStorage.getItem(key) === sessionId) return;
      sessionStorage.setItem(key, sessionId);
    } catch {
      // The in-memory ref still prevents repeated alerts when storage is unavailable.
    }
    announced.current = sessionId;
    setNoticeSession(sessionId);
    pushToast('Session ready', 'Your VPN profile is available on the VPN page.', 'success');
  }, [sessionId, pushToast]);

  return (
    <Modal open={Boolean(sessionId && noticeSession === sessionId)} onClose={close} size="small" title="Your session is ready">
      <p className="ui-dialog-message">Download your VPN profile from the VPN page to connect to your session.</p>
      <div className="ui-dialog-actions">
        <Button onClick={close} variant="ghost">Later</Button>
        <Button onClick={() => { close(); navigate('/vpn'); }} variant="primary">Go to VPN page</Button>
      </div>
    </Modal>
  );
}

function ProtectedRoute() {
  const { isAuthenticated, isAuthInitializing } = useApp();
  const location = useLocation();

  if (isAuthInitializing) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--ink)' }}>
        <p style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }}>Verifying operator credentials...</p>
      </div>
    );
  }

  return isAuthenticated ? <PlatformLayout /> : <Navigate replace state={{ from: location.pathname }} to="/login" />;
}

function PublicAuthRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAuthInitializing } = useApp();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  if (isAuthInitializing) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--ink)' }}>
        <p style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }}>Loading...</p>
      </div>
    );
  }

  return isAuthenticated ? <Navigate replace to={from} /> : <>{children}</>;
}

function PassagePage() {
  return (
    <main className="not-found-page" style={{ textAlign: 'center', maxWidth: '640px', margin: '0 auto', minHeight: '80vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '2rem' }}>
      <span className="platform-eyebrow" style={{ color: 'var(--lime)' }}>YOU FOUND THE PASSAGE</span>
      <h1 style={{ margin: '1rem 0' }}>The monument is only the surface.<br /><em>Look where the water used to be.</em></h1>
      <p style={{ color: 'var(--muted)', fontSize: '0.95rem', lineHeight: 1.7 }}>
        "When the reflection disappears, examine the residual cache."
      </p>
      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--lime)', marginTop: '2rem', padding: '0.5rem 1rem', background: 'var(--panel-deep)', borderRadius: 'var(--radius)', border: '1px solid var(--line)', display: 'inline-block' }}>
        TARGET GATEWAY: 10.42.0.0/24 — ACTIVE THRESHOLD
      </code>
      <div style={{ marginTop: '2rem' }}>
        <a className="ui-button ui-button-secondary ui-button-medium" href="/challenges">
          Return to investigation
        </a>
      </div>
    </main>
  );
}

function NotFoundPage() {
  return (
    <div className="not-found-page">
      <span className="platform-eyebrow">Signal not found / 404</span>
      <h1>Nothing here<br /><em>but silence.</em></h1>
      <p>The route you requested is outside the current observation layer.</p>
      <a className="ui-button ui-button-primary ui-button-medium" href="/">
        Return to the surface
      </a>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route element={<LandingPage />} path="/" />
        <Route element={<LandingPage />} path="/explore" />

        {/* Auth routes */}
        <Route element={<AuthLayout><PublicAuthRoute><LoginPage /></PublicAuthRoute></AuthLayout>} path="/login" />
        <Route element={<Navigate replace to="/login" />} path="/otp-login" />
        <Route element={<Navigate replace to="/login" />} path="/register" />
        <Route element={<AuthLayout><PublicAuthRoute><VerifyOtpPage /></PublicAuthRoute></AuthLayout>} path="/verify-otp" />
        <Route element={<Navigate replace to="/login" />} path="/forgot-password" />
        <Route element={<Navigate replace to="/login" />} path="/reset-password" />

        {/* Protected Dashboard and Workspace routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardPage />} path="/dashboard" />
          <Route element={<VpnPage />} path="/vpn" />
          <Route element={<ChallengesPage />} path="/challenges" />
          <Route element={<ChallengeDetailPage />} path="/challenges/:id" />
          <Route element={<SessionsPage />} path="/sessions" />
          <Route element={<Navigate replace to="/sessions" />} path="/session" />
          <Route element={<LeaderboardPage />} path="/leaderboard" />
          <Route element={<DocsPage />} path="/docs" />
          <Route element={<ProfilePage />} path="/profile" />
          <Route element={<SettingsPage />} path="/settings" />
        </Route>

        {/* Easter Egg & 404 */}
        <Route element={<PassagePage />} path="/passage" />
        <Route element={<NotFoundPage />} path="*" />
      </Routes>
      <SessionReadyNotice />
      <ToastViewport />
      <AvailabilityNotice />
    </BrowserRouter>
  );
}
