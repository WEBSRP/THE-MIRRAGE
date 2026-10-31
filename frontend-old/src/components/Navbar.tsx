import { Link, useLocation } from 'react-router-dom';
import { MirrageLogo } from './MirrageLogo';
import { ThemeToggle } from './ThemeToggle';
import { useAuth } from '../contexts/AuthContext';

/**
 * Navbar — Public top navigation bar.
 * Matches reference: MIRRAGE logo left, nav links center-right, Sign In button right.
 * Back arrow on left when not on home page.
 */
export function Navbar() {
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const isHome = location.pathname === '/';

  const navLinks = [
    { to: '/explore', label: 'Explore' },
    { to: '/challenges', label: 'Challenges' },
    { to: '/leaderboard', label: 'Leaderboard' },
    { to: '/docs', label: 'Docs' },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[var(--nav-bg)] backdrop-blur-sm border-b border-[var(--border)]/50">
      <nav className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Left: Back arrow + Logo */}
        <div className="flex items-center gap-4">
          {!isHome && (
            <Link
              to="/"
              className="text-[var(--text-muted)] hover:text-[var(--text)] transition-colors text-sm"
              aria-label="Back to home"
            >
              ←
            </Link>
          )}
          <Link to="/" className="flex items-center">
            <MirrageLogo size="md" />
          </Link>
        </div>

        {/* Center: Nav links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`text-[13px] transition-colors ${
                location.pathname === link.to
                  ? 'text-[var(--text)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)]'
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Right: Theme toggle + Auth */}
        <div className="flex items-center gap-3">
          <ThemeToggle />
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="btn-outline text-xs px-3 py-1.5"
            >
              Dashboard
            </Link>
          ) : (
            <Link
              to="/login"
              className="btn-outline text-xs px-3 py-1.5"
            >
              Sign In
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
