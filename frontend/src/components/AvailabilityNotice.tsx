import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon';
import './availability-notice.css';

const DISMISSED_KEY = 'mirrage-availability-notice-dismissed';
const socialProfiles = [
  { label: 'LinkedIn', logo: 'linkedin', url: 'https://www.linkedin.com/in/websrp/', override: import.meta.env.VITE_CONTACT_LINKEDIN_URL },
  { label: 'X', logo: 'x', url: 'https://x.com/websrp', override: import.meta.env.VITE_CONTACT_TWITTER_URL },
  { label: 'Instagram', logo: 'instagram', url: 'https://www.instagram.com/in_soum_niaaaa/', override: import.meta.env.VITE_CONTACT_INSTAGRAM_URL },
];

function SocialLogo({ platform }: { platform: string }) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">
      {platform === 'linkedin' ? (
        <path fill="currentColor" d="M20.45 2H3.55C2.69 2 2 2.68 2 3.52v16.96C2 21.32 2.69 22 3.55 22h16.9c.86 0 1.55-.68 1.55-1.52V3.52C22 2.68 21.31 2 20.45 2ZM7.93 18.75H4.98V9.2h2.95v9.55ZM6.46 7.9a1.71 1.71 0 1 1 0-3.42 1.71 1.71 0 0 1 0 3.42Zm12.29 10.85H15.8V14.1c0-1.11-.02-2.54-1.55-2.54-1.55 0-1.79 1.21-1.79 2.46v4.73H9.51V9.2h2.83v1.3h.04c.39-.74 1.36-1.52 2.79-1.52 2.98 0 3.58 1.96 3.58 4.51v5.26Z" />
      ) : platform === 'x' ? (
        <path fill="currentColor" d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.64 7.584H.47l8.6-9.835L0 1.154h7.594l5.243 6.932 6.064-6.933ZM17.61 20.644h2.039L6.486 3.24H4.298L17.61 20.644Z" />
      ) : (
        <g fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="5" />
          <circle cx="12" cy="12" r="4" />
          <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
        </g>
      )}
    </svg>
  );
}

function profileUrl(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export function AvailabilityNotice() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISSED_KEY) !== 'true';
    } catch {
      return true;
    }
  });

  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const dismiss = () => {
    try {
      sessionStorage.setItem(DISMISSED_KEY, 'true');
    } catch {
      // The notice can still be dismissed when browser storage is unavailable.
    }
    setOpen(false);
  };

  if (!open) return null;

  return (
    <dialog ref={dialogRef} className="availability-notice" aria-labelledby="availability-title"
      aria-describedby="availability-description" onCancel={(event) => { event.preventDefault(); dismiss(); }}>
      <div className="availability-notice-topline">
        <span className="availability-notice-label"><Icon name="info" size={15} /> Project notice</span>
        <button type="button" className="availability-notice-close" onClick={dismiss} aria-label="Close notice">
          <Icon name="x" size={18} />
        </button>
      </div>
      <h2 id="availability-title">Your next challenge.<br /><em>Available on demand.</em></h2>
      <p id="availability-description">
        MIRRAGE is an independent educational project with challenge environments available on
        request. Ready to explore? Send me a message on any of the social platforms below with
        your preferred date, time, and time zone, and we’ll arrange a time to bring the lab online.
      </p>
      <p className="availability-notice-example">“Hi! I’d like to play MIRRAGE on [date] at [time + time zone].”</p>
      <nav className="availability-notice-socials" aria-label="Social contact profiles">
        {socialProfiles.map(({ label, logo, url, override }) => (
            <a key={label} href={profileUrl(override) || url} target="_blank" rel="noopener noreferrer"
              aria-label={`Message me on ${label} (opens in a new tab)`} title={label}>
              <SocialLogo platform={logo} />
            </a>
        ))}
      </nav>
      <button autoFocus type="button" className="ui-button ui-button-primary ui-button-large availability-notice-continue" onClick={dismiss}>
        Got it — explore MIRRAGE <Icon name="arrow-right" size={16} />
      </button>
    </dialog>
  );
}
