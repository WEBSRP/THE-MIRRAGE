import { type ReactNode } from 'react';
import { Navbar } from '../components/Navbar';

/**
 * MainLayout — Wraps public-facing pages with the top navbar.
 * No footer — the design is clean and minimal.
 */
export function MainLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--bg)]">
      <Navbar />
      <main className="pt-14">
        {children}
      </main>
    </div>
  );
}
