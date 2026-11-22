import { Link } from 'react-router-dom';
import { contactProfiles } from '../data/socialProfiles';
import { Mark } from './Icon';
import './site-footer.css';

export function SiteFooter({ backToTop = false }: { backToTop?: boolean }) {
  return (
    <footer className="mirrage-footer">
      <Link className="wordmark" to="/" aria-label="MIRRAGE home"><Mark /><span>MIRRAGE</span></Link>
      <nav aria-label="Site information">
        <Link to="/about">About us</Link>
        <Link to="/privacy">Privacy policy</Link>
        {backToTop && <a href="#top">Back to top ↑</a>}
      </nav>
      <nav aria-label="Social links">
        {contactProfiles.map(({ label, href }) => (
          <a key={label} href={href} target="_blank" rel="noopener noreferrer" aria-label={`${label} (opens in a new tab)`}>
            {label}
          </a>
        ))}
      </nav>
    </footer>
  );
}
