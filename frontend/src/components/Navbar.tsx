import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useScrollPosition } from '../hooks/useScrollPosition';
import { MirrageLogo } from './MirrageLogo';

export function Navbar() {
  const { isScrolled } = useScrollPosition();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  const isHome = location.pathname === '/';
  const navBackground =
    isScrolled || !isHome
      ? 'bg-[var(--obsidian)]/90 backdrop-blur-md border-b border-[var(--gold-muted)]/15 shadow-xl'
      : 'bg-gradient-to-b from-[var(--obsidian)]/80 via-[var(--obsidian)]/40 to-transparent';

  const navLinks = [
    { label: 'ABOUT', href: '/about' },
    { label: 'ARCHIVE', href: '/archive' },
    { label: 'EXPLORE', href: '/explore' },
    { label: 'ENTER', href: '/enter' },
  ];

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${navBackground}`}
    >
      <div className="max-w-7xl mx-auto px-6 sm:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo with Geometric Icon */}
          <Link
            to="/"
            className="group flex items-center gap-3 font-display text-xl sm:text-2xl tracking-[0.25em] text-[var(--sandstone-light)] hover:text-[var(--gold-muted)] transition-colors duration-300"
          >
            <MirrageLogo size={32} />
            <span>MIRRAGE</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8 lg:gap-10">
            {navLinks.map((link) => {
              const isActive = location.pathname === link.href;
              const isEnter = link.label === 'ENTER';

              if (isEnter) {
                return (
                  <Link
                    key={link.href}
                    to={link.href}
                    className="px-5 py-2 border border-[var(--gold-muted)]/50 bg-[var(--gold-muted)]/10 hover:bg-[var(--gold-muted)] hover:text-[var(--obsidian)] text-xs font-semibold tracking-[0.2em] text-[var(--gold-muted)] transition-all duration-300"
                  >
                    ENTER
                  </Link>
                );
              }

              return (
                <Link
                  key={link.href}
                  to={link.href}
                  className={`text-xs font-medium tracking-[0.2em] transition-colors duration-300 ${
                    isActive
                      ? 'text-[var(--gold-muted)] font-semibold'
                      : 'text-[var(--sandstone-light)]/80 hover:text-[var(--sandstone-light)]'
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden flex flex-col gap-1.5 p-2 rounded focus:outline-none"
            aria-label="Toggle navigation menu"
            aria-expanded={isMobileMenuOpen}
          >
            <span
              className={`block w-6 h-0.5 bg-[var(--sandstone-light)] transition-all duration-300 ${
                isMobileMenuOpen ? 'rotate-45 translate-y-2' : ''
              }`}
            />
            <span
              className={`block w-6 h-0.5 bg-[var(--sandstone-light)] transition-all duration-300 ${
                isMobileMenuOpen ? 'opacity-0' : ''
              }`}
            />
            <span
              className={`block w-6 h-0.5 bg-[var(--sandstone-light)] transition-all duration-300 ${
                isMobileMenuOpen ? '-rotate-45 -translate-y-2' : ''
              }`}
            />
          </button>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      <div
        className={`md:hidden overflow-hidden transition-all duration-300 ${
          isMobileMenuOpen ? 'max-h-80 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="bg-[var(--obsidian)]/98 backdrop-blur-xl border-t border-[var(--gold-muted)]/15 px-6 py-6 space-y-4 shadow-2xl">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              onClick={() => setIsMobileMenuOpen(false)}
              className={`block text-sm font-medium tracking-[0.15em] transition-colors duration-300 ${
                location.pathname === link.href
                  ? 'text-[var(--gold-muted)]'
                  : 'text-[var(--sandstone-light)]/80 hover:text-[var(--sandstone-light)]'
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
