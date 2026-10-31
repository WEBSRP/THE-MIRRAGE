import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { MonolithIllustration } from '../components/Illustrations';

export function HomePage() {
  const { theme } = useTheme();

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg)] overflow-hidden relative">
      <div className="flex-1 flex w-full max-w-7xl mx-auto px-6 py-12 relative z-10">
        
        {/* Left column */}
        <div className="hidden md:flex flex-col justify-between items-center w-12 border-r border-[var(--border)] mr-12 pb-12">
          <div className="flex-1 flex items-center pt-12">
            <div 
              className="font-mono text-[10px] tracking-[0.2em] uppercase text-[var(--text-faint)] flex gap-4 rotate-180" 
              style={{ writingMode: 'vertical-rl' }}
            >
              <span>DISCOVER</span>
              <span>ANALYZE</span>
              <span>EXPLOIT</span>
              <span>LEARN</span>
              <span>REPEAT</span>
            </div>
          </div>
          <div className="font-mono text-[10px] text-[var(--text-faint)]">01</div>
        </div>

        {/* Center content */}
        <div className="flex-1 flex flex-col justify-center animate-fade-in relative z-10">
          <h1 className="font-serif text-5xl md:text-6xl lg:text-7xl text-[var(--text)] leading-tight whitespace-pre-line mb-6">
            {theme === 'night' 
              ? 'YOU ARE LOOKING\nAT THE WRONG THING.' 
              : 'SAME ILLUSION.\nA DEEPER REALITY.'}
          </h1>
          <p className="text-[var(--text-muted)] text-sm max-w-md mb-12 leading-relaxed">
            A controlled environment for exploring what was designed to remain unnoticed.
          </p>
          
          <div className="flex flex-wrap gap-4 font-mono text-xs uppercase tracking-wider">
            <Link 
              to="/login" 
              className="px-6 py-3 bg-[var(--accent)] text-[#0B0D0F] hover:opacity-90 transition-opacity rounded-sm font-semibold"
            >
              Enter the Environment →
            </Link>
            <Link 
              to="/challenges" 
              className="px-6 py-3 border border-[var(--border)] text-[var(--text)] hover:bg-[var(--surface)] transition-colors rounded-sm"
            >
              Explore Challenges
            </Link>
          </div>
        </div>

        {/* Right side Illustration */}
        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-72 md:w-96 opacity-40 pointer-events-none">
          <MonolithIllustration />
        </div>
      </div>

      {/* Bottom stats bar */}
      <div className="border-t border-[var(--border)] bg-[var(--bg)] relative z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-wrap gap-8 font-mono text-[11px] text-[var(--text-faint)] uppercase tracking-widest">
          <div className="flex items-center gap-2">
            <span className="text-lg text-[var(--text)]">03</span>
            <span>Environments</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg text-[var(--text)]">12</span>
            <span>Active Sessions</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg text-[var(--text)]">1,427</span>
            <span>Events Captured</span>
          </div>
        </div>
      </div>
    </div>
  );
}
