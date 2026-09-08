import { useState, type ReactNode } from 'react';
import { DashboardSidebar } from '../components/DashboardSidebar';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../contexts/AuthContext';
import { MirrageLogo } from '../components/MirrageLogo';

export function DashboardLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col md:flex-row">
      <DashboardSidebar isOpen={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />
      
      {/* Main content */}
      <div className="flex-1 md:ml-52 flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="h-14 shrink-0 border-b border-[var(--border)]/30 flex items-center justify-between md:justify-end px-4 md:px-6 gap-3 bg-[var(--bg)] sticky top-0 z-20">
          <div className="flex items-center gap-3 md:hidden">
            <button onClick={() => setMobileMenuOpen(true)} className="text-[var(--text-muted)] p-1">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
            </button>
            <MirrageLogo size="sm" />
          </div>
          
          <div className="flex items-center gap-3">
            <ThemeToggle />
            {user && (
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-[var(--accent)] flex items-center justify-center text-[11px] text-[var(--bg)] font-medium">
                  {user.username.charAt(0).toUpperCase()}
                </div>
                <span className="hidden sm:inline text-[12px] text-[var(--text-muted)]">{user.username}</span>
              </div>
            )}
          </div>
        </header>
        <main className="p-4 md:p-8 flex-1 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
