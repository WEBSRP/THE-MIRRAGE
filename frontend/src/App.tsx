import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import { MainLayout } from './layouts/MainLayout';
import { DashboardLayout } from './layouts/DashboardLayout';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { SessionPage } from './pages/SessionPage';
import { DashboardPage } from './pages/DashboardPage';
import { ChallengesPage } from './pages/ChallengesPage';
import { ChallengeDetailPage } from './pages/ChallengeDetailPage';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { DocsPage } from './pages/DocsPage';
import { ProfilePage } from './pages/ProfilePage';
import { VpnPage } from './pages/VpnPage';

/**
 * ProtectedRoute — Redirects to /login if not authenticated.
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <p className="text-[var(--text-faint)] text-sm animate-pulse-subtle">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      {/* ─── Public routes (MainLayout with top navbar) ─── */}
      <Route path="/" element={<MainLayout><HomePage /></MainLayout>} />
      <Route path="/explore" element={<MainLayout><HomePage /></MainLayout>} />

      {/* ─── Auth routes (own layout) ─── */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* ─── Session init (own layout) ─── */}
      <Route path="/session" element={
        <ProtectedRoute><SessionPage /></ProtectedRoute>
      } />

      {/* ─── Dashboard routes (sidebar layout) ─── */}
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <DashboardLayout><DashboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/challenges" element={
        <ProtectedRoute>
          <DashboardLayout><ChallengesPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/challenges/:slug" element={
        <ProtectedRoute>
          <DashboardLayout><ChallengeDetailPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/leaderboard" element={
        <ProtectedRoute>
          <DashboardLayout><LeaderboardPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/docs" element={
        <ProtectedRoute>
          <DashboardLayout><DocsPage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/profile" element={
        <ProtectedRoute>
          <DashboardLayout><ProfilePage /></DashboardLayout>
        </ProtectedRoute>
      } />
      <Route path="/vpn" element={
        <ProtectedRoute>
          <DashboardLayout><VpnPage /></DashboardLayout>
        </ProtectedRoute>
      } />

      {/* ─── Hidden route — easter egg ─── */}
      <Route
        path="/passage"
        element={
          <main className="min-h-screen bg-[var(--bg)] flex items-center justify-center px-6">
            <div className="text-center animate-fade-in" style={{ animationDuration: '3s' }}>
              <p className="text-[var(--accent)] text-sm tracking-wider uppercase mb-4 font-medium">
                YOU FOUND THE PASSAGE
              </p>
              <p className="text-[var(--text-muted)] text-base max-w-md mx-auto leading-relaxed">
                "The monument is only the surface. When the reflection disappears, look where the water used to be."
              </p>
              <p className="text-[var(--text-faint)]/40 text-xs tracking-wider mt-8 font-mono">
                TARGET GATEWAY: 10.42.0.0/24 — ACTIVE THRESHOLD
              </p>
            </div>
          </main>
        }
      />

      {/* ─── 404 ─── */}
      <Route
        path="*"
        element={
          <main className="min-h-screen bg-[var(--bg)] flex items-center justify-center px-6">
            <div className="text-center">
              <h1 className="font-serif text-6xl text-[var(--text-faint)]/40 mb-4">
                404
              </h1>
              <p className="text-base text-[var(--text-muted)] tracking-wide">
                Nothing here but silence.
              </p>
            </div>
          </main>
        }
      />
    </Routes>
  );
}

export default App;
