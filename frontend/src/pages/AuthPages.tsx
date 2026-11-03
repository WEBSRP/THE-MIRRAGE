import { useState, useEffect, useRef, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Button, Card, PasswordField, TextField } from '../components/ui';
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
  const { login, requestOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    const result = await login(identifier, password);
    if (!result.ok) {
      setError(result.message ?? 'Unable to sign in.');
      return;
    }
    navigate(from, { replace: true });
  };

  const handleOtp = async () => {
    if (!identifier.includes('@')) {
      setError('Enter your email address first to request a one-time verification code.');
      return;
    }
    setError('');
    const result = await requestOtp(identifier);
    if (!result.ok) {
      setError(result.message ?? 'Unable to send a code.');
      return;
    }
    navigate('/verify-otp', { state: { email: identifier, from } });
  };

  return (
    <div className="auth-form-wrap">
      <AuthIntro
        eyebrow="01 / access"
        title={<>Welcome back,<br /><em>operator.</em></>}
        copy="The range is active. Sign in with password or request a one-time verification code."
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        {error ? (
          <div className="auth-alert auth-alert-error">
            <Icon name="info" size={16} />
            <span>{error}</span>
          </div>
        ) : null}
        <TextField
          autoComplete="username"
          label="Email or username"
          onChange={(event) => setIdentifier(event.target.value)}
          placeholder="you@example.com"
          required
          value={identifier}
        />
        <PasswordField
          autoComplete="current-password"
          label="Password"
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter your password"
          required
          value={password}
        />
        <div className="auth-form-meta">
          <button className="auth-text-button" onClick={handleOtp} type="button">
            Use email code <Icon name="arrow-up-right" size={13} />
          </button>
        </div>
        <Button className="auth-submit" loading={isAuthLoading} size="large" type="submit" variant="primary">
          Enter the range <Icon name="arrow-right" size={16} />
        </Button>
      </form>
      <div className="auth-switch">
        New to the range? <Link to="/register">Create an operator account <Icon name="arrow-up-right" size={14} /></Link>
      </div>
    </div>
  );
}

export function RegisterPage() {
  const { register, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const [details, setDetails] = useState({ name: '', username: '', email: '', password: '', confirm: '' });
  const [error, setError] = useState('');

  const update = (key: keyof typeof details, value: string) =>
    setDetails((current) => ({ ...current, [key]: value }));

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (details.password.length < 8) {
      setError('Use at least 8 characters for your password.');
      return;
    }
    if (details.password !== details.confirm) {
      setError('Password confirmation does not match.');
      return;
    }
    const result = await register(details);
    if (!result.ok) {
      setError(result.message ?? 'Unable to create account.');
      return;
    }
    navigate('/dashboard', { replace: true });
  };

  return (
    <div className="auth-form-wrap">
      <AuthIntro
        eyebrow="02 / registration"
        title={<>Make your<br /><em>own signal.</em></>}
        copy="Create an operator profile. Your persistent identity and OpenVPN certificates are initialized upon registration."
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        {error ? (
          <div className="auth-alert auth-alert-error">
            <Icon name="info" size={16} />
            <span>{error}</span>
          </div>
        ) : null}
        <div className="auth-form-grid">
          <TextField
            autoComplete="name"
            label="Full name"
            onChange={(event) => update('name', event.target.value)}
            placeholder="Avery Chen"
            required
            value={details.name}
          />
          <TextField
            autoComplete="username"
            label="Username"
            onChange={(event) => update('username', event.target.value)}
            placeholder="aetherline"
            required
            value={details.username}
          />
        </div>
        <TextField
          autoComplete="email"
          label="Email address"
          onChange={(event) => update('email', event.target.value)}
          placeholder="you@somewhere.com"
          required
          type="email"
          value={details.email}
        />
        <div className="auth-form-grid">
          <PasswordField
            autoComplete="new-password"
            label="Password"
            onChange={(event) => update('password', event.target.value)}
            placeholder="8+ characters"
            required
            value={details.password}
          />
          <PasswordField
            autoComplete="new-password"
            label="Confirm password"
            onChange={(event) => update('confirm', event.target.value)}
            placeholder="Repeat password"
            required
            value={details.confirm}
          />
        </div>
        <label className="ui-checkbox">
          <input required type="checkbox" />
          <span className="ui-checkmark">
            <Icon name="check" size={12} />
          </span>
          <span>I understand this is an isolated cybersecurity range.</span>
        </label>
        <Button className="auth-submit" loading={isAuthLoading} size="large" type="submit" variant="primary">
          Create operator account <Icon name="arrow-right" size={16} />
        </Button>
      </form>
      <div className="auth-switch">
        Already have access? <Link to="/login">Return to sign in <Icon name="arrow-up-right" size={14} /></Link>
      </div>
    </div>
  );
}

export function VerifyOtpPage() {
  const { requestOtp, verifyOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const email = (location.state as { email?: string } | null)?.email ?? '';
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(email ? `Verification code sent to ${email}.` : 'Enter the code sent to your email.');
  const [countdown, setCountdown] = useState(60);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (countdown > 0) {
      timerRef.current = window.setTimeout(() => setCountdown((c) => c - 1), 1000);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [countdown]);

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

  const resend = async () => {
    if (countdown > 0 || !email) return;
    setError('');
    const result = await requestOtp(email);
    if (!result.ok) {
      setError(result.message ?? 'Could not resend verification code.');
    } else {
      setCountdown(60);
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
        <button
          className="auth-resend"
          disabled={isAuthLoading || countdown > 0}
          onClick={resend}
          type="button"
        >
          {countdown > 0 ? `Resend code in ${countdown}s` : 'Resend code'} <Icon name="refresh" size={13} />
        </button>
      </form>
      <div className="auth-switch">
        <Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link>
      </div>
    </div>
  );
}

export function ForgotPasswordPage() {
  const { requestOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    const result = await requestOtp(email);
    if (!result.ok) {
      setError(result.message ?? 'Enter a valid email.');
    } else {
      setSuccess(true);
    }
  };

  return (
    <div className="auth-form-wrap auth-form-narrow">
      <AuthIntro
        eyebrow="04 / recovery"
        title={<>Passwordless<br /><em>access.</em></>}
        copy="Request a one-time verification code to sign in directly without needing your password."
      />
      {!success ? (
        <form className="auth-form" onSubmit={handleSubmit}>
          {error ? (
            <div className="auth-alert auth-alert-error">
              <Icon name="info" size={16} />
              <span>{error}</span>
            </div>
          ) : null}
          <TextField
            autoComplete="email"
            label="Account email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            required
            type="email"
            value={email}
          />
          <Button className="auth-submit" loading={isAuthLoading} size="large" type="submit" variant="primary">
            Send verification code <Icon name="send" size={16} />
          </Button>
        </form>
      ) : (
        <Card className="auth-success-card">
          <span className="auth-success-icon"><Icon name="check" size={20} /></span>
          <h3>Verification code sent.</h3>
          <p>A 6-digit login code has been dispatched to <strong>{email}</strong>.</p>
          <Button onClick={() => navigate('/verify-otp', { state: { email } })} variant="primary">
            Enter code <Icon name="arrow-right" size={15} />
          </Button>
        </Card>
      )}
      <div className="auth-switch">
        <Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link>
      </div>
    </div>
  );
}

export function ResetPasswordPage() {
  const { resetPassword, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    const result = await resetPassword(password);
    if (!result.ok) {
      setError(result.message ?? 'Unable to reset password.');
    } else {
      setSuccess(true);
    }
  };

  return (
    <div className="auth-form-wrap auth-form-narrow">
      <AuthIntro
        eyebrow="05 / reset"
        title={<>Set a new<br /><em>passphrase.</em></>}
        copy="Enter a secure password for your operator account."
      />
      {!success ? (
        <form className="auth-form" onSubmit={handleSubmit}>
          {error ? (
            <div className="auth-alert auth-alert-error">
              <Icon name="info" size={16} />
              <span>{error}</span>
            </div>
          ) : null}
          <PasswordField
            autoComplete="new-password"
            label="New password"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="8+ characters"
            required
            value={password}
          />
          <PasswordField
            autoComplete="new-password"
            label="Confirm new password"
            onChange={(event) => setConfirm(event.target.value)}
            placeholder="Repeat password"
            required
            value={confirm}
          />
          <Button className="auth-submit" loading={isAuthLoading} size="large" type="submit" variant="primary">
            Save new password <Icon name="check" size={16} />
          </Button>
        </form>
      ) : (
        <Card className="auth-success-card">
          <span className="auth-success-icon"><Icon name="check" size={20} /></span>
          <h3>Password updated.</h3>
          <p>Your password has been changed. Use it the next time you sign in.</p>
          <Button onClick={() => navigate('/login')} variant="primary">
            Return to sign in <Icon name="arrow-right" size={15} />
          </Button>
        </Card>
      )}
      <div className="auth-switch">
        <Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link>
      </div>
    </div>
  );
}
