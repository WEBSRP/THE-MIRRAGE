import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon, Mark, Wordmark } from '../components/Icon';
import { useApp, useTheme } from '../state/AppState';
import { DesignStudio } from '../design-system/DesignStudio';
import { InteractiveSignalCore } from '../design-system/InteractiveVisuals';
import './landing-space.css';

export function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { challenges, isAuthenticated, solvedChallengeIds } = useApp();
  const [studioOpen, setStudioOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const closeStudio = useCallback(() => setStudioOpen(false), []);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [menuOpen]);

  return (
    <div className="landing-space" id="top">
      <a className="landing-skip" href="#landing-main">Skip to content</a>
      <header className="landing-header">
        <Link className="wordmark" to="/" aria-label="MIRRAGE home"><Mark /><span>MIRRAGE</span></Link>
        <nav aria-label="Public navigation" id="landing-nav" className={`landing-nav ${menuOpen ? 'is-open' : ''}`}>
          <a href="#range" onClick={() => setMenuOpen(false)}>The range</a>
          <a href="#targets" onClick={() => setMenuOpen(false)}>Challenges</a>
          <Link to="/login" onClick={() => setMenuOpen(false)}>{isAuthenticated ? 'Workspace' : 'Sign in'}</Link>
        </nav>
        <div className="landing-header-actions">
          <button className="landing-design-button" onClick={() => setStudioOpen(true)} type="button">
            <Icon name="spark" size={14} /><span>Explore Designs</span>
          </button>
          <button className="landing-icon-button" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} onClick={toggleTheme} type="button">
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={17} />
          </button>
          <button className="landing-icon-button landing-menu-button" aria-controls="landing-nav" aria-expanded={menuOpen} aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} onClick={() => setMenuOpen((value) => !value)} type="button">
            <Icon name={menuOpen ? 'x' : 'menu'} size={20} />
          </button>
        </div>
      </header>

      <main id="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-hero-copy">
            <p className="landing-kicker"><span /> Beyond the surface</p>
            <h1 id="landing-title">Find what<br /><em>is hidden.</em></h1>
            <p className="landing-intro">A space for curious minds to explore cybersecurity. Follow the signal. Question the obvious.</p>
            <Link className="landing-primary" to={isAuthenticated ? '/dashboard' : '/login'}>
              {isAuthenticated ? 'Return to workspace' : 'Enter the range'}<Icon name="arrow-up-right" size={18} />
            </Link>
            <p className="landing-demo-note">Cluster connected · Isolated Kubernetes environments.</p>
          </div>
          <div className="landing-hero-art"><InteractiveSignalCore /></div>
          <a className="landing-scroll-note" href="#range"><span>01 — Look a little closer</span><Icon name="arrow-right" size={14} /></a>
        </section>

        <section className="landing-range" id="range" aria-labelledby="range-title">
          <div className="landing-range-copy">
            <p className="landing-kicker">The observation layer</p>
            <h2 id="range-title">Less noise.<br /><em>More discovery.</em></h2>
            <p>Think beyond the checklist. Explore active targets, investigate available services, and build your own approach to solving each challenge.</p>
          </div>
          <div className="landing-principles" id="operations">
            <article><span>01</span><div><h3>A space to experiment.</h3><p>Launch your private CTF machine and explore at your own pace.</p></div></article>
            <article><span>02</span><div><h3>Follow your curiosity.</h3><p>Practice reconnaissance, web exploitation, and forensics as you capture flags.</p></div></article>
            <article><span>03</span><div><h3>Keep the whole picture.</h3><p>Stream live OpenVPN network telemetry and cluster session activity in real time.</p></div></article>
          </div>
        </section>

        <section className="landing-targets" id="targets" aria-labelledby="targets-title">
          <div className="landing-section-heading">
            <div><p className="landing-kicker">A few starting points</p><h2 id="targets-title">Choose a signal.</h2></div>
            <Link className="landing-text-link" to="/challenges">All challenges<Icon name="arrow-up-right" size={16} /></Link>
          </div>
          <div className="landing-target-list">
            {challenges.slice(0, 3).map((challenge, index) => (
              <Link className="landing-target" key={challenge.id} to={`/challenges/${challenge.id}`}>
                <span className="landing-target-index">0{index + 1}</span>
                <span className="landing-target-name"><strong>{challenge.title}</strong><small>{challenge.category} · {challenge.difficulty}</small></span>
                <span className="landing-target-points">{solvedChallengeIds.includes(challenge.id) ? 'Solved' : `${challenge.points} pts`}</span>
                <Icon name="arrow-up-right" size={19} />
              </Link>
            ))}
          </div>
        </section>

        <section className="landing-invitation" aria-labelledby="invitation-title">
          <p className="landing-kicker">Your next perspective</p>
          <h2 id="invitation-title">Stay curious.</h2>
          <Link className="landing-text-link" to={isAuthenticated ? '/dashboard' : '/register'}>
            {isAuthenticated ? 'Continue exploring' : 'Create an operator account'}<Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <Wordmark link={false} />
        <span>MIRRAGE / Cybersecurity CTF Range</span>
        <a href="#top">Back to top ↑</a>
      </footer>
      <DesignStudio open={studioOpen} onClose={closeStudio} />
    </div>
  );
}
