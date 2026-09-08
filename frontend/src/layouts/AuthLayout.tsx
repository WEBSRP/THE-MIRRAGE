import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { MirrageLogo } from '../components/MirrageLogo';
import { GatewayIllustration } from '../components/Illustrations';

/**
 * AuthLayout — Layout for login/register pages.
 * Reference: MIRRAGE logo top-left, "← Back to Home" top-right,
 * left side has decorative vertical text + illustration,
 * right side has the auth form.
 */
export function AuthLayout({
  children,
  sideText,
  sideCaption,
}: {
  children: ReactNode;
  sideText: string;
  sideCaption?: string;
}) {
  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col">
      {/* Top bar */}
      <header className="px-6 h-14 flex items-center justify-between border-b border-[var(--border)]/30">
        <Link to="/" className="flex items-center">
          <MirrageLogo size="md" />
        </Link>
        <Link
          to="/"
          className="text-[13px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
        >
          ← Back to Home
        </Link>
      </header>

      {/* Content */}
      <div className="flex-1 flex">
        {/* Left side — decorative */}
        <div className="hidden lg:flex flex-col justify-between w-[40%] max-w-md p-12 relative">
          {/* Vertical text */}
          <div className="space-y-1">
            {sideText.split('\n').map((line, i) => (
              <p key={i} className="font-mono text-[11px] text-[var(--text-faint)] tracking-[0.2em] uppercase leading-relaxed">
                {line}
              </p>
            ))}
          </div>

          {/* Illustration */}
          <div className="flex justify-center">
            <GatewayIllustration className="w-28 opacity-40" />
          </div>

          {/* Caption */}
          {sideCaption && (
            <p className="text-[12px] text-[var(--text-faint)] leading-relaxed">
              {sideCaption}
            </p>
          )}
        </div>

        {/* Right side — form */}
        <div className="flex-1 flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-sm">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
