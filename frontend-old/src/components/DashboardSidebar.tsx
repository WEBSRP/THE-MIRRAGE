import { Link, useLocation } from 'react-router-dom';
import { MirrageLogo } from './MirrageLogo';
import { ThemeToggle } from './ThemeToggle';
import { useAuth } from '../contexts/AuthContext';

/**
 * DashboardSidebar — Left sidebar navigation for authenticated pages.
 * Matches reference: MIRRAGE logo top, nav items with icons, vertical text at bottom.
 */

const sidebarLinks = [
  {
    to: '/dashboard',
    label: 'Home',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 6l6-4 6 4v7a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6Z" />
        <path d="M6 14V9h4v5" />
      </svg>
    ),
  },
  {
    to: '/challenges',
    label: 'Challenges',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 2h8l1 4-5 3-5-3 1-4Z" />
        <path d="M8 9v5" />
        <path d="M5 14h6" />
      </svg>
    ),
  },
  {
    to: '/leaderboard',
    label: 'Leaderboard',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="8" width="4" height="6" />
        <rect x="6" y="4" width="4" height="10" />
        <rect x="11" y="6" width="4" height="8" />
      </svg>
    ),
  },
  {
    to: '/docs',
    label: 'Docs',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 2h8l4 4v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V2Z" />
        <path d="M10 2v4h4" />
        <path d="M5 8h6M5 11h4" />
      </svg>
    ),
  },
  {
    to: '/vpn',
    label: 'VPN & Signal',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 1l6 3v4c0 3.5-2.5 6.5-6 8-3.5-1.5-6-4.5-6-8V4l6-3Z" />
      </svg>
    ),
  },
  {
    to: '/profile',
    label: 'Profile',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="8" cy="5" r="3" />
        <path d="M2 14c0-2.8 2.7-5 6-5s6 2.2 6 5" />
      </svg>
    ),
  },
];

export function DashboardSidebar({ isOpen, onClose }: { isOpen?: boolean; onClose?: () => void }) {
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-30 md:hidden backdrop-blur-sm"
          onClick={onClose}
        />
      )}
      
      <aside className={`fixed left-0 top-0 bottom-0 w-52 bg-[var(--surface)] border-r border-[var(--border)] flex flex-col z-40 transition-transform duration-300 md:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        {/* Logo */}
        <div className="px-5 h-14 flex items-center justify-between border-b border-[var(--border)]">
          <Link to="/" onClick={onClose}>
            <MirrageLogo size="md" />
          </Link>
          <button onClick={onClose} className="md:hidden text-[var(--text-muted)] p-1">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
          {sidebarLinks.map((link) => {
            const isActive = location.pathname === link.to || (link.to !== '/dashboard' && location.pathname.startsWith(link.to));
            return (
              <Link
                key={link.to}
                to={link.to}
                onClick={onClose}
                className={`flex items-center gap-3 px-3 py-2 rounded text-[13px] transition-colors ${
                  isActive
                    ? 'bg-[var(--accent-subtle)] text-[var(--accent)] border border-[var(--accent)]/15'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-alt)] border border-transparent'
                }`}
              >
                <span className={isActive ? 'text-[var(--accent)]' : ''}>{link.icon}</span>
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Bottom: vertical text + user */}
        <div className="px-3 pb-4 space-y-3">
          {/* Vertical motto text */}
          <p className="font-mono text-[9px] text-[var(--text-faint)] leading-[1.6] tracking-[0.15em] uppercase px-3">
            OBSERVATION<br />
            ENHANCES<br />
            UNDERSTANDING.
          </p>

          {/* User info + controls */}
          <div className="border-t border-[var(--border)] pt-3 px-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ThemeToggle />
              {user && (
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-[var(--accent)] flex items-center justify-center text-[10px] text-[var(--bg)] font-medium">
                    {user.username.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-[11px] text-[var(--text-muted)] truncate max-w-[60px]">
                    {user.username}
                  </span>
                </div>
              )}
            </div>
            <button
              onClick={logout}
              className="text-[11px] text-[var(--text-faint)] hover:text-[var(--danger)] transition-colors cursor-pointer"
              title="Sign out"
            >
              ↗
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
