import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon';
import './availability-notice.css';

const DISMISSED_KEY = 'mirrage-availability-notice-dismissed';
const socialProfiles = [
  { label: 'LinkedIn', url: import.meta.env.VITE_CONTACT_LINKEDIN_URL },
  { label: 'X / Twitter', url: import.meta.env.VITE_CONTACT_TWITTER_URL },
  { label: 'Threads', url: import.meta.env.VITE_CONTACT_THREADS_URL },
  { label: 'Instagram', url: import.meta.env.VITE_CONTACT_INSTAGRAM_URL },
];

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
        {socialProfiles.map(({ label, url }) => {
          const href = profileUrl(url);
          return href ? (
            <a key={label} href={href} target="_blank" rel="noopener noreferrer">
              {label}<Icon name="arrow-up-right" size={14} />
            </a>
          ) : <span key={label} className="availability-notice-unconfigured">{label}</span>;
        })}
      </nav>
      {!socialProfiles.some(({ url }) => profileUrl(url)) ? (
        <p className="availability-notice-contact-note">Contact profile links will be added soon.</p>
      ) : null}
      <button autoFocus type="button" className="ui-button ui-button-primary ui-button-large availability-notice-continue" onClick={dismiss}>
        Got it — explore MIRRAGE <Icon name="arrow-right" size={16} />
      </button>
    </dialog>
  );
}
