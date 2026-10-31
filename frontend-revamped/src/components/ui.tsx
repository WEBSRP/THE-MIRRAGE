import { useEffect, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react';
import { Icon, type IconName } from './Icon';
import { useApp } from '../state/AppState';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';

export function Button({ variant = 'secondary', size = 'medium', loading = false, icon, children, disabled, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'small' | 'medium' | 'large'; loading?: boolean; icon?: IconName }) {
  return (
    <button className={`ui-button ui-button-${variant} ui-button-${size} ${className}`} disabled={disabled || loading} {...props}>
      {loading ? <Icon className="ui-spin" name="loader" size={16} /> : icon ? <Icon name={icon} size={16} /> : null}
      {loading ? 'Working…' : children}
    </button>
  );
}

export function IconButton({ label, icon, active = false, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon: IconName; active?: boolean }) {
  return <button aria-label={label} className={`ui-icon-button ${active ? 'is-active' : ''} ${className}`} {...props}><Icon name={icon} size={17} /></button>;
}

export function Card({ children, className = '', padding = 'medium' }: { children: ReactNode; className?: string; padding?: 'none' | 'small' | 'medium' | 'large' }) {
  return <section className={`ui-card ui-card-${padding} ${className}`}>{children}</section>;
}

export function Badge({ children, tone = 'muted', dot = false }: { children: ReactNode; tone?: 'lime' | 'blue' | 'orange' | 'red' | 'muted' | 'purple'; dot?: boolean }) {
  return <span className={`ui-badge ui-badge-${tone}`}>{dot ? <span className="ui-badge-dot" /> : null}{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone = normalized.includes('ready') || normalized.includes('connected') || normalized.includes('solved') || normalized.includes('operational') ? 'lime' : normalized.includes('starting') || normalized.includes('connecting') || normalized.includes('stopping') ? 'orange' : normalized.includes('error') || normalized.includes('expired') ? 'red' : 'muted';
  return <Badge dot tone={tone}>{status}</Badge>;
}

export function TextField({ label, error, hint, icon, className = '', ...props }: InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string; hint?: string; icon?: IconName }) {
  return (
    <label className={`ui-field ${error ? 'has-error' : ''} ${className}`}>
      {label ? <span className="ui-field-label">{label}{props.required ? <em> *</em> : null}</span> : null}
      <span className="ui-input-wrap">{icon ? <Icon name={icon} size={16} /> : null}<input {...props} /> </span>
      {error ? <span className="ui-field-message ui-field-error"><Icon name="info" size={13} />{error}</span> : hint ? <span className="ui-field-message">{hint}</span> : null}
    </label>
  );
}

export function SelectField({ label, options, error, className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label?: string; options: Array<{ value: string; label: string }>; error?: string }) {
  return (
    <label className={`ui-field ${error ? 'has-error' : ''} ${className}`}>
      {label ? <span className="ui-field-label">{label}</span> : null}
      <span className="ui-input-wrap ui-select-wrap"><select {...props}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><Icon name="chevron-down" size={15} /></span>
      {error ? <span className="ui-field-message ui-field-error"><Icon name="info" size={13} />{error}</span> : null}
    </label>
  );
}

export function PasswordField({ label, error, ...props }: InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string }) {
  const [visible, setVisible] = useState(false);
  return <div className="ui-password-control"><TextField {...props} label={label} error={error} type={visible ? 'text' : 'password'} className="ui-password-field" /><button aria-label={visible ? 'Hide password' : 'Show password'} className="ui-password-toggle" onClick={() => setVisible((current) => !current)} type="button"><Icon name={visible ? 'eye-off' : 'eye'} size={16} /></button></div>;
}

export function ProgressBar({ value, label, tone = 'lime' }: { value: number; label?: string; tone?: 'lime' | 'blue' | 'orange' }) {
  return <div className="ui-progress-wrap">{label ? <div className="ui-progress-label"><span>{label}</span><strong>{Math.round(value)}%</strong></div> : null}<div className="ui-progress"><span className={`ui-progress-fill ui-progress-${tone}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div></div>;
}

export function EmptyState({ icon = 'search', title, message, action }: { icon?: IconName; title: string; message: string; action?: ReactNode }) {
  return <div className="ui-empty"><span className="ui-empty-icon"><Icon name={icon} size={23} /></span><h3>{title}</h3><p>{message}</p>{action}</div>;
}

export function LoadingState({ label = 'Loading simulated data…' }: { label?: string }) {
  return <div className="ui-loading"><Icon className="ui-spin" name="loader" size={19} /><span>{label}</span></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="ui-error-state"><Icon name="info" size={18} /><div><strong>Something needs another look</strong><p>{message}</p>{onRetry ? <Button onClick={onRetry} size="small" variant="secondary" icon="refresh">Try again</Button> : null}</div></div>;
}

export function Modal({ open, title, children, onClose, size = 'medium', className = '' }: { open: boolean; title?: string; children: ReactNode; onClose: () => void; size?: 'small' | 'medium' | 'large'; className?: string }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKeyDown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    return () => { document.removeEventListener('keydown', onKeyDown); document.body.style.overflow = originalOverflow; };
  }, [onClose, open]);
  if (!open) return null;
  return <div className="ui-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }} role="presentation"><div aria-modal="true" className={`ui-modal ui-modal-${size} ${className}`} ref={dialogRef} role="dialog" tabIndex={-1}><div className="ui-modal-header">{title ? <h2>{title}</h2> : <span /> }<IconButton label="Close dialog" icon="x" onClick={onClose} /></div>{children}</div></div>;
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel, loading = false }: { open: boolean; title: string; message: string; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onCancel: () => void; loading?: boolean }) {
  return <Modal open={open} title={title} onClose={onCancel} size="small"><p className="ui-dialog-message">{message}</p><div className="ui-dialog-actions"><Button onClick={onCancel} variant="ghost">Cancel</Button><Button onClick={onConfirm} variant={danger ? 'danger' : 'primary'} loading={loading}>{confirmLabel}</Button></div></Modal>;
}

export function ToastViewport() {
  const { toasts, dismissToast } = useApp();
  return <div aria-live="polite" className="ui-toast-viewport">{toasts.map((toast) => <div className={`ui-toast ui-toast-${toast.tone}`} key={toast.id}><span className="ui-toast-icon"><Icon name={toast.tone === 'success' ? 'check' : toast.tone === 'error' ? 'info' : 'activity'} size={15} /></span><div><strong>{toast.title}</strong><p>{toast.message}</p></div><button aria-label="Dismiss notification" onClick={() => dismissToast(toast.id)} type="button"><Icon name="x" size={14} /></button></div>)}</div>;
}
