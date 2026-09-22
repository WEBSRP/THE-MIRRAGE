import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, Navigate } from 'react-router-dom';
import { AuthLayout } from '../layouts/AuthLayout';
import { requestOtp, resendOtp } from '../services/authService';
import { useAuth } from '../contexts/AuthContext';

export function OtpLoginPage() {
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [countdown, setCountdown] = useState(0);

  const timerRef = useRef<number | null>(null);
  const navigate = useNavigate();
  const { otpLogin, isAuthenticated } = useAuth();

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
      const result = await otpLogin(email, otp);
      if (result.is_new_user) {
        // Just as a future-proof step, though instruction says to go to dashboard
        navigate('/dashboard');
      } else {
        navigate('/dashboard');
      }
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

  return (
    <AuthLayout
      sideText={'VERIFY\nYOUR\nPRESENCE.'}
      sideCaption="Confirm your identity."
    >
      <div className="w-full max-w-md mx-auto">
        <div className="mb-8">
          <h1 className="font-serif text-2xl mb-2 text-[var(--text)]">
            {step === 1 ? 'Passwordless Sign In' : 'Enter Verification Code'}
          </h1>
          <p className="text-[var(--text-muted)] text-sm">
            {step === 1 ? 'We will send a 6-digit code to your email' : `Code sent to ${maskEmail(email)}`}
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

        {step === 1 ? (
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
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || !email}
              className="btn-primary w-full !mt-6"
            >
              {isLoading ? 'Sending...' : 'Send Verification Code'}
            </button>
          </form>
        ) : (
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
                className={`text-sm ${countdown > 0 ? 'text-[var(--text-faint)]' : 'text-[var(--accent)] hover:underline'}`}
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
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
              >
                Use a different email
              </button>
            </div>
          </form>
        )}

        <div className="mt-8 text-center text-sm text-[var(--text-muted)]">
          Or{' '}
          <Link to="/login" className="text-[var(--accent)] hover:underline">
            sign in with password
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
