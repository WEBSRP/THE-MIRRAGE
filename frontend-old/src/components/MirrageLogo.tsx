/**
 * MirrageLogo — Clean wordmark, no Egyptian imagery.
 * Monospace-inspired, all-caps "MIRRAGE" with subtle tracking.
 */
export function MirrageLogo({ className = '', size = 'md' }: { className?: string; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'text-base',
    md: 'text-lg',
    lg: 'text-xl',
  };

  return (
    <span
      className={`font-serif tracking-[0.08em] text-[var(--text)] select-none ${sizeClasses[size]} ${className}`}
    >
      MIRRAGE
    </span>
  );
}
