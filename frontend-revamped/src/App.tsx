import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ToastViewport } from './components/ui';
import { AuthLayout, PlatformLayout } from './layouts/PlatformLayout';
import { LandingPage } from './pages/LandingPage';
import { ChallengeDetailPage, ChallengesPage } from './pages/ChallengesPages';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, VerifyOtpPage } from './pages/AuthPages';
import { DashboardPage } from './pages/DashboardPage';
import { VpnPage } from './pages/VpnPage';
import { SessionsPage } from './pages/SessionsPage';
import { ProfilePage, SettingsPage } from './pages/AccountPages';
import { useApp } from './state/AppState';

function ProtectedRoute() {
  const { isAuthenticated } = useApp();
  const location = useLocation();
  return isAuthenticated ? <PlatformLayout /> : <Navigate replace state={{ from: location.pathname }} to="/login" />;
}

function PublicAuthRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useApp();
  return isAuthenticated ? <Navigate replace to="/dashboard" /> : <>{children}</>;
}

function NotFoundPage() {
  return <div className="not-found-page"><span className="platform-eyebrow">Signal not found / 404</span><h1>Nothing here<br /><em>but silence.</em></h1><p>The route you requested is outside the current observation layer.</p><a className="ui-button ui-button-primary ui-button-medium" href="/">Return to the surface</a></div>;
}

export default function App() {
  return <BrowserRouter><Routes><Route element={<LandingPage />} path="/" /><Route element={<LandingPage />} path="/explore" /><Route element={<AuthLayout><PublicAuthRoute><LoginPage /></PublicAuthRoute></AuthLayout>} path="/login" /><Route element={<AuthLayout><PublicAuthRoute><RegisterPage /></PublicAuthRoute></AuthLayout>} path="/register" /><Route element={<AuthLayout><PublicAuthRoute><VerifyOtpPage /></PublicAuthRoute></AuthLayout>} path="/verify-otp" /><Route element={<AuthLayout><PublicAuthRoute><ForgotPasswordPage /></PublicAuthRoute></AuthLayout>} path="/forgot-password" /><Route element={<AuthLayout><PublicAuthRoute><ResetPasswordPage /></PublicAuthRoute></AuthLayout>} path="/reset-password" /><Route element={<ProtectedRoute />}><Route element={<DashboardPage />} path="/dashboard" /><Route element={<VpnPage />} path="/vpn" /><Route element={<ChallengesPage />} path="/challenges" /><Route element={<ChallengeDetailPage />} path="/challenges/:id" /><Route element={<SessionsPage />} path="/sessions" /><Route element={<ProfilePage />} path="/profile" /><Route element={<SettingsPage />} path="/settings" /></Route><Route element={<NotFoundPage />} path="*" /></Routes><ToastViewport /></BrowserRouter>;
}
