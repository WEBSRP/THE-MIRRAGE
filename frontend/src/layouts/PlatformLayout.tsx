import { useState, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Icon, Wordmark, type IconName } from '../components/Icon';
import { Badge, IconButton } from '../components/ui';
import { useApp, useTheme } from '../state/AppState';
import { DesignStudio } from '../design-system/DesignStudio';
import './workspace-space.css';

type NavItem = { label: string; path: string; icon: IconName; end?: boolean; badge?: string };

const primaryNav: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: 'home', end: true },
  { label: 'Challenges', path: '/challenges', icon: 'shield' },
  { label: 'Sessions', path: '/sessions', icon: 'server' },
  { label: 'VPN workspace', path: '/vpn', icon: 'vpn' },
  { label: 'Leaderboard', path: '/leaderboard', icon: 'activity' },
  { label: 'Docs', path: '/docs', icon: 'terminal' },
];

const secondaryNav: NavItem[] = [
  { label: 'Profile', path: '/profile', icon: 'user' },
  { label: 'Settings', path: '/settings', icon: 'settings' },
];

export function PlatformLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const { user, logout, activities } = useApp();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);
  const newActivityCount = activities.filter((activity) => activity.timestamp === 'Just now').length;

  const closeMenus = () => { setMobileOpen(false); setNotificationsOpen(false); setAccountOpen(false); };

  return (
    <div className={`platform-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <div className={`platform-mobile-backdrop ${mobileOpen ? 'is-visible' : ''}`} onClick={() => setMobileOpen(false)} role="presentation" />
      <aside className={`platform-sidebar ${mobileOpen ? 'is-mobile-open' : ''}`}>
        <div className="platform-sidebar-brand"><Wordmark /><button aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} className="platform-collapse" onClick={() => setSidebarCollapsed((current) => !current)} type="button"><Icon name={sidebarCollapsed ? 'chevron-right' : 'chevron-left'} size={16} /></button></div>
        <div className="platform-sidebar-scroll">
          <div className="platform-nav-group"><span className="platform-nav-label">Workspace</span>{primaryNav.map((item) => <SidebarLink item={item} key={item.path} onClick={closeMenus} />)}</div>
          <div className="platform-nav-group"><span className="platform-nav-label">Account</span>{secondaryNav.map((item) => <SidebarLink item={item} key={item.path} onClick={closeMenus} />)}</div>
        </div>
        <div className="platform-sidebar-foot">
          <div className="platform-sim-badge"><span className="live-dot" style={{ backgroundColor: 'var(--lime)' }} /><div><strong>MIRRAGE LIVE</strong><small>Cluster connected</small></div></div>
          <button className="platform-user-mini" onClick={() => { navigate('/profile'); closeMenus(); }} type="button"><span className="platform-avatar">{user.avatar}</span><span className="platform-user-mini-copy"><strong>{user.username}</strong><small>{user.points.toLocaleString()} points</small></span><Icon name="chevron-right" size={14} /></button>
        </div>
      </aside>

      <div className="platform-main">
        <header className="platform-topbar">
          <div className="platform-topbar-left"><button aria-label="Open navigation" className="platform-mobile-menu" onClick={() => setMobileOpen(true)} type="button"><Icon name="menu" size={20} /></button><div className="platform-breadcrumb"><span>Workspace</span><Icon name="chevron-right" size={13} /><strong>{pageTitle}</strong></div></div>
          <div className="platform-topbar-actions">
            <button aria-label="Design Studio" className="platform-studio-trigger" onClick={() => setStudioOpen(true)} type="button"><Icon name="spark" size={15} /><span>Design Studio</span></button>
            <button aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} aria-pressed={theme === 'light'} className="platform-theme-toggle" onClick={toggleTheme} type="button"><Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} /><span>{theme === 'dark' ? 'Light' : 'Dark'}</span></button>
            <div className="platform-menu-wrap"><IconButton active={notificationsOpen} icon="bell" label="Open notifications" onClick={() => { setNotificationsOpen((current) => !current); setAccountOpen(false); }} />{newActivityCount > 0 ? <span className="platform-notification-count">{newActivityCount}</span> : null}{notificationsOpen ? <Dropdown className="platform-notification-menu"><div className="platform-dropdown-heading"><strong>Signals</strong><Badge tone="lime">{newActivityCount} new</Badge></div>{activities.slice(0, 3).map((activity) => <button className="platform-notification-item" key={activity.id} onClick={() => { navigate('/dashboard'); closeMenus(); }} type="button"><span className={`activity-dot activity-dot-${activity.tone}`} /><span><strong>{activity.title}</strong><small>{activity.detail}</small></span></button>)}</Dropdown> : null}</div>
            <div className="platform-menu-wrap"><button className="platform-account-button" onClick={() => { setAccountOpen((current) => !current); setNotificationsOpen(false); }} type="button"><span className="platform-avatar">{user.avatar}</span><span className="platform-account-copy"><strong>{user.username}</strong><small>{user.role}</small></span><Icon name="chevron-down" size={14} /></button>{accountOpen ? <Dropdown className="platform-account-menu"><button onClick={() => { navigate('/profile'); closeMenus(); }} type="button"><Icon name="user" size={15} /> Profile</button><button onClick={() => { navigate('/settings'); closeMenus(); }} type="button"><Icon name="settings" size={15} /> Settings</button><div className="platform-dropdown-divider" /><button className="is-danger" onClick={() => { logout(); navigate('/login'); closeMenus(); }} type="button"><Icon name="logout" size={15} /> Log out</button></Dropdown> : null}</div>
          </div>
        </header>
        <main className="platform-content"><Outlet /></main>
      </div>
      <DesignStudio open={studioOpen} onClose={() => setStudioOpen(false)} />
    </div>
  );
}

function SidebarLink({ item, onClick }: { item: NavItem; onClick: () => void }) {
  return <NavLink className={({ isActive }) => `platform-nav-link ${isActive ? 'is-active' : ''}`} end={item.end} onClick={onClick} to={item.path}><Icon name={item.icon} size={17} /><span>{item.label}</span>{item.badge ? <Badge tone="orange">{item.badge}</Badge> : null}</NavLink>;
}

function Dropdown({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`platform-dropdown ${className}`}>{children}</div>;
}

export function AuthLayout({ children }: { children: ReactNode }) {
  return <div className="auth-shell"><div className="auth-promo"><div className="auth-promo-top"><Wordmark /></div><div className="auth-promo-content"><span className="eyebrow"><span className="eyebrow-line" /> Independent cyber range</span><h1>Think like<br /><em>an attacker.</em></h1><p>Private environments. Real signals. No scripted answers. Build a sharper mental model of the systems you defend.</p><div className="auth-promo-stats"><span><strong>128</strong><small>active targets</small></span><span><strong>03</strong><small>isolated layers</small></span><span><strong>24/7</strong><small>telemetry</small></span></div></div><div className="auth-promo-foot"><span><span className="live-dot" /> Simulation mode / no live connections</span><span>© 2026 MIRRAGE</span></div></div><div className="auth-panel"><div className="auth-panel-top"><NavLink className="auth-back-link" to="/"><Icon name="arrow-left" size={15} /> Back to surface</NavLink><ThemeControl /></div>{children}<div className="auth-panel-foot"><span>By continuing, you agree to our simulated environment terms.</span><span>Need a signal? <a href="mailto:hello@themirrage.me">Contact the team</a></span></div></div></div>;
}

function ThemeControl() {
  const { theme, toggleTheme } = useTheme();
  return <button aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} className="auth-theme-toggle" onClick={toggleTheme} type="button"><Icon name={theme === 'dark' ? 'sun' : 'moon'} size={15} /> {theme === 'dark' ? 'Light mode' : 'Dark mode'}</button>;
}

function getPageTitle(pathname: string) {
  if (pathname.startsWith('/challenges/')) return 'Challenge detail';
  const match = [...primaryNav, ...secondaryNav].find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`));
  return match?.label ?? 'Workspace';
}
