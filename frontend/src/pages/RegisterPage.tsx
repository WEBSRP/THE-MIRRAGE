import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register } from '../services/authService';
import { AuthLayout } from '../layouts/AuthLayout';

export function RegisterPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);
    try {
      await register({ username, email, password });
      navigate('/login', { state: { message: 'Registration successful. Please sign in.' } });
    } catch (err: any) {
      setError(err.response?.data?.message || err.message || 'Registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout
      sideText={'CURIOSITY\nREQUIRES\nA START.'}
      sideCaption="Join the MIRRAGE program."
    >
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="font-serif text-2xl text-[var(--text)]">Create Account</h1>
          <p className="text-[var(--text-muted)] text-sm mt-1">Begin your journey.</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] transition-colors pr-14"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text)] text-xs uppercase"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
              Confirm Password
            </label>
            <div className="relative">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded px-3 py-2 text-[var(--text)] focus:outline-none focus:border-[var(--accent)] transition-colors pr-14"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text)] text-xs uppercase"
              >
                {showConfirmPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          {error && (
            <div className="text-red-500 text-sm p-3 bg-red-500/10 border border-red-500/20 rounded">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-[var(--accent)] text-[#0B0D0F] font-medium py-2 rounded hover:bg-opacity-90 transition-colors disabled:opacity-50 mt-2"
          >
            {isLoading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="text-center text-sm text-[var(--text-muted)]">
          Already have an account?{' '}
          <Link to="/login" className="text-[var(--accent)] hover:underline">
            Sign in
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
