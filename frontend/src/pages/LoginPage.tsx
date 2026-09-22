import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, Navigate } from 'react-router-dom';
import { AuthLayout } from '../layouts/AuthLayout';
import { requestOtp, resendOtp, login as passwordLogin, devLogin } from '../services/authService';
import { useAuth } from '../contexts/AuthContext';

type LoginMode = 'otp' | 'password';

export function LoginPage() {
  const [mode, setMode] = useState<LoginMode>('otp');

  // OTP state
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [successMsg, setSuccessMsg] = useState('');

  // Password state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Shared state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const timerRef = useRef<number | null>(null);
  const navigate = useNavigate();
  const { setUser, otpLogin, isAuthenticated } = useAuth();

  useEffect(() => {
    if (countdown > 0) {
      timerRef.current = window.setTimeout(() => setCountdown(c => c - 1), 1000);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [countdown]);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const maskEmail = (em: string) => {
    if (!em || !em.includes('@')) return em;
    const [user, domain] = em.split('@');
    if (user.length <= 1) return `${user}***@${domain}`;
    return `${user.charAt(0)}***@${domain}`;
  };

  const switchMode = (newMode: LoginMode) => {
    setMode(newMode);
    setError('');
    setSuccessMsg('');
    setOtp('');
    setStep(1);
  };

  // ── OTP Handlers ──
  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await requestOtp(email);
      setSuccessMsg('Verification code sent to your email.');
      setStep(2);
      setCountdown(60);
    } catch (err: any) {
      setError(err.message || 'Failed to send OTP');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (otp.length !== 6 || !/^\d+$/.test(otp)) {
      setError('Please enter a valid 6-digit code');
      return;
    }

    setIsLoading(true);
    try {
      await otpLogin(email, otp);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to verify code');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0) return;
    setError('');
    setIsLoading(true);
    try {
      await resendOtp(email);
      setCountdown(60);
      setSuccessMsg('A new verification code has been sent.');
    } catch (err: any) {
      setError(err.message || 'Failed to resend code');
    } finally {
      setIsLoading(false);
    }
  };

  // ── Password Handler ──
  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await passwordLogin({ username_or_email: username, password });
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
          <h1 className="font-serif text-2xl mb-2 text-[var(--text)]">
            {mode === 'otp'
              ? step === 1
                ? 'Welcome'
                : 'Enter Verification Code'
              : 'Password Sign In'}
          </h1>
          <p className="text-[var(--text-muted)] text-sm">
            {mode === 'otp'
              ? step === 1
                ? 'Sign in with a verification code sent to your email'
                : `Code sent to ${maskEmail(email)}`
              : 'Sign in with your username or email and password'}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-[var(--danger-subtle)] border border-[var(--danger)]/50 rounded text-[var(--danger)] text-sm">
            {error}
          </div>
        )}

        {successMsg && (
          <div className="mb-6 p-3 bg-[var(--surface)] border border-[var(--accent)]/50 rounded text-[var(--accent)] text-sm">
            {successMsg}
          </div>
        )}

        {/* ── OTP Mode ── */}
        {mode === 'otp' && step === 1 && (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div>
              <label className="block text-xs font-mono mb-1 text-[var(--text-muted)] tracking-wider">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-none transition-colors"
                placeholder="you@example.com"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || !email}
              className="btn-primary w-full !mt-6"
            >
              {isLoading ? 'Sending...' : 'Continue with Email'}
            </button>
          </form>
        )}

        {mode === 'otp' && step === 2 && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <div>
              <label className="block text-xs font-mono mb-1 text-[var(--text-muted)] tracking-wider">
                6-Digit Code
              </label>
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-none transition-colors tracking-widest font-mono text-center text-lg"
                placeholder="000000"
                maxLength={6}
                autoFocus
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || otp.length !== 6}
              className="btn-primary w-full !mt-6"
            >
              {isLoading ? 'Verifying...' : 'Verify'}
            </button>

            <div className="flex flex-col items-center gap-2 mt-4">
              <button
                type="button"
                onClick={handleResend}
                disabled={countdown > 0 || isLoading}
                className={`text-sm ${countdown > 0 ? 'text-[var(--text-faint)]' : 'text-[var(--accent)] hover:underline cursor-pointer'}`}
              >
                {countdown > 0 ? `Resend Code (${countdown}s)` : 'Resend Code'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setStep(1);
                  setOtp('');
                  setError('');
                  setSuccessMsg('');
                }}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
              >
                Use a different email
              </button>
            </div>
          </form>
        )}

        {/* ── Password Mode ── */}
        {mode === 'password' && (
          <form onSubmit={handlePasswordLogin} className="space-y-4">
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
        )}

        {/* ── Mode Switch & Registration ── */}
        <div className="mt-8 space-y-3 text-center text-sm text-[var(--text-muted)]">
          {mode === 'otp' ? (
            <p>
              Or{' '}
              <button
                type="button"
                onClick={() => switchMode('password')}
                className="text-[var(--accent)] hover:underline cursor-pointer"
              >
                use password instead
              </button>
            </p>
          ) : (
            <p>
              Or{' '}
              <button
                type="button"
                onClick={() => switchMode('otp')}
                className="text-[var(--accent)] hover:underline cursor-pointer"
              >
                sign in with email code
              </button>
            </p>
          )}

          <p>
            Don't have an account?{' '}
            <Link to="/register" className="text-[var(--accent)] hover:underline">
              Create one
            </Link>
          </p>
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
