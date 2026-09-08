import { useState } from 'react';
import { useNavigate, Link, Navigate } from 'react-router-dom';
import { AuthLayout } from '../layouts/AuthLayout';
import { login, devLogin } from '../services/authService';
import { useAuth } from '../contexts/AuthContext';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const navigate = useNavigate();
  const { setUser, isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await login({ username_or_email: username, password });
      setUser(result.user);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to sign in');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDevLogin = async () => {
    setError('');
    try {
      const result = await devLogin();
      setUser(result.user);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed dev login');
    }
  };

  return (
    <AuthLayout
      sideText={'SOME\nTHINGS\nARE BETTER\nLEFT\nUNSEEN.'}
      sideCaption="Continue your investigation."
    >
      <div className="w-full max-w-md mx-auto">
        <div className="mb-8">
          <h1 className="font-serif text-2xl mb-2 text-[var(--text)]">Welcome Back</h1>
          <p className="text-[var(--text-muted)] text-sm">Sign in to your account</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-[var(--danger-subtle)] border border-[var(--danger)]/50 rounded text-[var(--danger)] text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono mb-1 text-[var(--text-muted)]">
              Email or Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-none transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-mono mb-1 text-[var(--text-muted)]">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-none transition-colors pr-10"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text)] cursor-pointer flex items-center justify-center"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                    <line x1="1" y1="1" x2="23" y2="23"></line>
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary w-full !mt-6"
          >
            {isLoading ? 'Signing In...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-[var(--text-muted)]">
          Don't have an account?{' '}
          <Link to="/register" className="text-[var(--accent)] hover:underline">
            Create one
          </Link>
        </div>

        {import.meta.env.DEV && (
          <div className="mt-12 pt-6 border-t border-white/10">
            <button
              onClick={handleDevLogin}
              type="button"
              className="w-full border border-dashed border-[var(--accent)] text-[var(--accent)] text-xs py-2 px-4 rounded hover:bg-[var(--accent)] hover:bg-opacity-10 transition-colors"
            >
              Development Access (dev_player)
            </button>
            <p className="text-center text-[10px] text-[var(--text-muted)] mt-2">
              For local development only
            </p>
          </div>
        )}
      </div>
    </AuthLayout>
  );
}
