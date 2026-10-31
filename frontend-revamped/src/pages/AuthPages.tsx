import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Button, Card, PasswordField, TextField } from '../components/ui';
import { DEMO_OTP, DEMO_PASSWORD } from '../data/mockData';
import { useApp, mockCredentials } from '../state/AppState';

function AuthIntro({ eyebrow, title, copy }: { eyebrow: string; title: ReactNode; copy: string }) {
  return <div className="auth-form-intro"><span className="auth-eyebrow">{eyebrow}</span><h2>{title}</h2><p>{copy}</p></div>;
}

export function LoginPage() {
  const { login, requestOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');
    const result = await login(identifier, password);
    if (!result.ok) { setError(result.message ?? 'Unable to sign in.'); return; }
    navigate(from, { replace: true });
  };

  const useDemo = () => { setIdentifier(mockCredentials.email); setPassword(DEMO_PASSWORD); setError(''); setNotice('Demo credentials loaded. Submit to enter the simulated workspace.'); };

  const handleOtp = async () => {
    if (!identifier.includes('@')) { setError('Enter your email first to request a one-time code.'); return; }
    const result = await requestOtp(identifier);
    if (!result.ok) { setError(result.message ?? 'Unable to send a code.'); return; }
    navigate('/verify-otp', { state: { email: identifier, from } });
  };

  return <div className="auth-form-wrap"><AuthIntro eyebrow="01 / access" title={<>Welcome back,<br /><em>operator.</em></>} copy="The range is waiting. Sign in to continue where you left the signal." />
    <form className="auth-form" onSubmit={handleSubmit}>
      {error ? <div className="auth-alert auth-alert-error"><Icon name="info" size={16} /><span>{error}</span></div> : null}
      {notice ? <div className="auth-alert auth-alert-success"><Icon name="check" size={16} /><span>{notice}</span></div> : null}
      <TextField autoComplete="username" label="Email or username" onChange={(event) => setIdentifier(event.target.value)} placeholder="operator@mirrage.me" required value={identifier} />
      <PasswordField autoComplete="current-password" label="Password" onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required value={password} />
      <div className="auth-form-meta"><Link to="/forgot-password">Forgot password?</Link><button className="auth-text-button" onClick={handleOtp} type="button">Use a one-time code <Icon name="arrow-up-right" size={13} /></button></div>
      <Button className="auth-submit" loading={isAuthLoading} type="submit" variant="primary" size="large">Enter the range <Icon name="arrow-right" size={16} /></Button>
      <button className="demo-credentials" onClick={useDemo} type="button"><span><Icon name="spark" size={14} /> Try the demo account</span><small>{mockCredentials.email} / {DEMO_PASSWORD}</small></button>
    </form>
    <div className="auth-switch">New to the range? <Link to="/register">Create an operator account <Icon name="arrow-up-right" size={14} /></Link></div>
  </div>;
}

export function RegisterPage() {
  const { register, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const [details, setDetails] = useState({ name: '', username: '', email: '', password: '', confirm: '' });
  const [error, setError] = useState('');
  const update = (key: keyof typeof details, value: string) => setDetails((current) => ({ ...current, [key]: value }));
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (details.password.length < 8) { setError('Use at least 8 characters for your password.'); return; }
    if (details.password !== details.confirm) { setError('Password confirmation does not match.'); return; }
    const result = await register(details);
    if (!result.ok) { setError(result.message ?? 'Unable to create account.'); return; }
    navigate('/dashboard', { replace: true });
  };
  return <div className="auth-form-wrap"><AuthIntro eyebrow="02 / registration" title={<>Make your<br /><em>own signal.</em></>} copy="Create a local demo operator profile. No account or credential is sent anywhere." />
    <form className="auth-form" onSubmit={handleSubmit}>
      {error ? <div className="auth-alert auth-alert-error"><Icon name="info" size={16} /><span>{error}</span></div> : null}
      <div className="auth-form-grid"><TextField autoComplete="name" label="Full name" onChange={(event) => update('name', event.target.value)} placeholder="Avery Chen" required value={details.name} /><TextField autoComplete="username" label="Username" onChange={(event) => update('username', event.target.value)} placeholder="aetherline" required value={details.username} /></div>
      <TextField autoComplete="email" label="Email address" onChange={(event) => update('email', event.target.value)} placeholder="you@somewhere.com" required type="email" value={details.email} />
      <div className="auth-form-grid"><PasswordField autoComplete="new-password" label="Password" onChange={(event) => update('password', event.target.value)} placeholder="8+ characters" required value={details.password} /><PasswordField autoComplete="new-password" label="Confirm password" onChange={(event) => update('confirm', event.target.value)} placeholder="Repeat password" required value={details.confirm} /></div>
      <label className="ui-checkbox"><input required type="checkbox" /><span className="ui-checkmark"><Icon name="check" size={12} /></span><span>I understand this is a simulated training environment.</span></label>
      <Button className="auth-submit" loading={isAuthLoading} type="submit" variant="primary" size="large">Create operator account <Icon name="arrow-right" size={16} /></Button>
    </form>
    <div className="auth-switch">Already have access? <Link to="/login">Return to sign in <Icon name="arrow-up-right" size={14} /></Link></div>
  </div>;
}

export function VerifyOtpPage() {
  const { requestOtp, verifyOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const email = (location.state as { email?: string } | null)?.email ?? mockCredentials.email;
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(`A simulated code was sent to ${email}.`);
  const [resent, setResent] = useState(false);
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (!/^\d{6}$/.test(code)) { setError('Enter the six-digit verification code.'); return; }
    const result = await verifyOtp(code);
    if (!result.ok) { setError(result.message ?? 'That code was not accepted.'); return; }
    navigate(from, { replace: true });
  };
  const resend = async () => { setError(''); const result = await requestOtp(email); if (!result.ok) setError(result.message ?? 'Could not resend the code.'); else { setResent(true); setNotice('A fresh simulated code was sent. Use 424242.'); } };
  return <div className="auth-form-wrap auth-form-narrow"><AuthIntro eyebrow="03 / verification" title={<>Verify the<br /><em>signal.</em></>} copy="Enter the six-digit code sent to your email. In this mock environment, it is always 424242." />
    <form className="auth-form" onSubmit={handleSubmit}>
      {error ? <div className="auth-alert auth-alert-error"><Icon name="info" size={16} /><span>{error}</span></div> : <div className="auth-alert auth-alert-success"><Icon name="check" size={16} /><span>{notice}</span></div>}
      <TextField autoComplete="one-time-code" inputMode="numeric" label="Verification code" maxLength={6} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} placeholder={DEMO_OTP} required value={code} />
      <Button className="auth-submit" loading={isAuthLoading} type="submit" variant="primary" size="large">Verify and continue <Icon name="arrow-right" size={16} /></Button>
      <button className="auth-resend" disabled={isAuthLoading || resent} onClick={resend} type="button">{resent ? 'Code resent' : 'Resend code'} <Icon name="refresh" size={13} /></button>
    </form>
    <div className="auth-switch"><Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link></div>
  </div>;
}

export function ForgotPasswordPage() {
  const { requestOtp, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setError(''); const result = await requestOtp(email); if (!result.ok) setError(result.message ?? 'Enter a valid email.'); else setSuccess(true); };
  return <div className="auth-form-wrap auth-form-narrow"><AuthIntro eyebrow="04 / recovery" title={<>Find your<br /><em>way back.</em></>} copy="Request a simulated password recovery signal. You can continue to the reset screen without an email service." />
    {!success ? <form className="auth-form" onSubmit={handleSubmit}>{error ? <div className="auth-alert auth-alert-error"><Icon name="info" size={16} /><span>{error}</span></div> : null}<TextField autoComplete="email" label="Account email" onChange={(event) => setEmail(event.target.value)} placeholder="operator@mirrage.me" required type="email" value={email} /><Button className="auth-submit" loading={isAuthLoading} type="submit" variant="primary" size="large">Send recovery signal <Icon name="send" size={16} /></Button></form> : <Card className="auth-success-card"><span className="auth-success-icon"><Icon name="check" size={20} /></span><h3>Recovery signal ready.</h3><p>In a real deployment, a link would arrive at <strong>{email}</strong>. This mock flow is ready to continue.</p><Button onClick={() => navigate('/reset-password')} variant="primary">Continue to reset <Icon name="arrow-right" size={15} /></Button></Card>}
    <div className="auth-switch"><Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link></div>
  </div>;
}

export function ResetPasswordPage() {
  const { resetPassword, isAuthLoading } = useApp();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setError(''); if (password !== confirm) { setError('Passwords do not match.'); return; } const result = await resetPassword(password); if (!result.ok) setError(result.message ?? 'Unable to reset password.'); else setSuccess(true); };
  return <div className="auth-form-wrap auth-form-narrow"><AuthIntro eyebrow="05 / reset" title={<>Set a new<br /><em>passphrase.</em></>} copy="This updates only the local demo state. No password is sent to a server." />
    {!success ? <form className="auth-form" onSubmit={handleSubmit}>{error ? <div className="auth-alert auth-alert-error"><Icon name="info" size={16} /><span>{error}</span></div> : null}<PasswordField autoComplete="new-password" label="New password" onChange={(event) => setPassword(event.target.value)} placeholder="8+ characters" required value={password} /><PasswordField autoComplete="new-password" label="Confirm new password" onChange={(event) => setConfirm(event.target.value)} placeholder="Repeat password" required value={confirm} /><Button className="auth-submit" loading={isAuthLoading} type="submit" variant="primary" size="large">Save new password <Icon name="check" size={16} /></Button></form> : <Card className="auth-success-card"><span className="auth-success-icon"><Icon name="check" size={20} /></span><h3>Passphrase updated.</h3><p>Your simulated password has been changed. Use it the next time you sign in.</p><Button onClick={() => navigate('/login')} variant="primary">Return to sign in <Icon name="arrow-right" size={15} /></Button></Card>}
    <div className="auth-switch"><Link to="/login"><Icon name="arrow-left" size={14} /> Back to sign in</Link></div>
  </div>;
}
