import { useState, useEffect, useRef, type FormEvent, type ReactNode } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Button, TextField } from '../components/ui';
import { useApp } from '../state/AppState';

function AuthIntro({ eyebrow, title, copy }: { eyebrow: string; title: ReactNode; copy: string }) {
  return (
    <div className="auth-form-intro">
      <span className="auth-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      <p>{copy}</p>
    </div>
  );
}

export function LoginPage() {
  const { requestOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    const normalizedEmail = email.trim().toLowerCase();
    const result = await requestOtp(normalizedEmail);
    if (!result.ok) {
      setError(result.message ?? 'Unable to send a verification code.');
      return;
    }
    navigate('/verify-otp', { state: { email: normalizedEmail, from, resendAt: Date.now() + (result.retryAfterSeconds ?? 0) * 1000 } });
  };

  return (
    <div className="auth-form-wrap">
      <AuthIntro eyebrow="01 / access" title={<>Enter the range,<br /><em>operator.</em></>}
        copy="Sign in with a one-time code sent to your email. New operators receive an account after verification." />
      <form className="auth-form" onSubmit={handleSubmit}>
        {error ? <div className="auth-alert auth-alert-error" role="alert"><Icon name="info" size={16} /><span>{error}</span></div> : null}
        <TextField autoComplete="email" label="Email address" type="email" required
          onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" value={email} />
        <Button className="auth-submit" loading={isAuthLoading} size="large" type="submit" variant="primary">
          Send verification code <Icon name="send" size={16} />
        </Button>
      </form>
    </div>
  );
}

export function VerifyOtpPage() {
  const { resendOtp, verifyOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const email = (location.state as { email?: string } | null)?.email ?? '';
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(email ? `Verification code sent to ${email}.` : 'Enter the code sent to your email.');
  const [resendAt, setResendAt] = useState((location.state as { resendAt?: number } | null)?.resendAt ?? 0);
  const [countdown, setCountdown] = useState(() => Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)));
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const update = () => setCountdown(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)));
    update();
    timerRef.current = window.setInterval(update, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [resendAt]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (!/^\d{6}$/.test(code)) {
      setError('Enter the 6-digit numeric verification code.');
      return;
    }
    const result = await verifyOtp(code, email);
    if (!result.ok) {
      setError(result.message ?? 'That code was not accepted.');
      return;
    }
    navigate(from, { replace: true });
  };

  if (!email) return <Navigate replace to="/login" />;

  const resend = async () => {
    if (countdown > 0 || !email) return;
    setError('');
    const result = await resendOtp(email);
    if (!result.ok) {
      setError(result.message ?? 'Could not resend verification code.');
      if (result.retryAfterSeconds) setResendAt(Date.now() + result.retryAfterSeconds * 1000);
    } else {
      setCode('');
      const deadline = Date.now() + (result.retryAfterSeconds ?? 60) * 1000;
      setResendAt(deadline);
      navigate('/verify-otp', { replace: true, state: { email, from, resendAt: deadline } });
      setNotice(`A fresh verification code was sent to ${email}.`);
    }
  };

  return (
    <div className="auth-form-wrap auth-form-narrow">
      <AuthIntro
        eyebrow="03 / verification"
        title={<>Verify your<br /><em>identity.</em></>}
        copy="Enter the 6-digit code sent to your email to authenticate without a password."
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        {error ? (
          <div className="auth-alert auth-alert-error">
            <Icon name="info" size={16} />
            <span>{error}</span>
          </div>
        ) : (
          <div className="auth-alert auth-alert-success">
            <Icon name="check" size={16} />
            <span>{notice}</span>
          </div>
        )}
        <button
          className="auth-resend"
          disabled={isAuthLoading || countdown > 0}
          onClick={resend}
          type="button"
        >
          {countdown > 0 ? `Resend code in ${countdown}s` : 'Resend code'} <Icon name="refresh" size={13} />
        </button>
        <TextField
          autoComplete="one-time-code"
          inputMode="numeric"
          label="Verification code"
          maxLength={6}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
          placeholder="000000"
          required
          value={code}
        />
        <Button className="auth-submit" loading={isAuthLoading} size="large" type="submit" variant="primary">
          Verify and continue <Icon name="arrow-right" size={16} />
        </Button>

      </form>
      <div className="auth-switch">
        <Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link>
      </div>
    </div>
  );
}
