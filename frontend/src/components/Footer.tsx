export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="relative border-t border-[var(--gold-muted)]/10 bg-[var(--obsidian)]">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-12 lg:py-16">
        <div className="flex flex-col md:flex-row justify-between items-center gap-8">
          {/* Logo and tagline */}
          <div className="text-center md:text-left">
            <p className="font-display text-lg tracking-widest text-[var(--sandstone-light)]">
              MIRRAGE
            </p>
            <p className="text-sm text-[var(--sandstone)]/50 mt-2">
              What you see is not what was built.
            </p>
          </div>

          {/* Mysterious symbols - decorative but one is a subtle easter egg */}
          <div className="flex items-center gap-6">
            {['𓂀', '𓁹', '𓋹', '𓂋'].map((symbol, i) => (
              <span
                key={i}
                className={`text-[var(--sandstone)]/20 text-lg hover:text-[var(--gold-muted)]/40 transition-colors duration-700 ${
                  i === 2 ? 'cursor-pointer' : ''
                }`}
                title={i === 2 ? 'Ankh — the key of life, or perhaps another key entirely' : undefined}
                data-glyph={i === 2 ? 'passage' : undefined}
              >
                {symbol}
              </span>
            ))}
          </div>

          {/* Copyright */}
          <div className="text-center md:text-right">
            <p className="text-sm text-[var(--sandstone)]/40">
              © {currentYear} MIRRAGE PROJECT
            </p>
            {/* Subtle inconsistency: the established date is in the future */}
            <p className="text-xs text-[var(--sandstone)]/20 mt-1">
              EST. 2847 BCE
            </p>
          </div>
        </div>

        {/* Hidden message in a seemingly decorative divider */}
        <div className="mt-12 pt-6 border-t border-[var(--gold-muted)]/5 text-center">
          <p className="text-[var(--sandstone)]/10 text-xs tracking-widest select-all">
            NOT EVERYTHING BURIED IS MEANT TO BE FOUND
          </p>
        </div>
      </div>
    </footer>
  );
}
