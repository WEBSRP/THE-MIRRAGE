import { type FC } from 'react';
import { Button } from './ui';
import { Icon } from './Icon';

interface EnvironmentLeaveGuardModalProps {
  isOpen: boolean;
  onStay: () => void;
  onStopAndLeave: () => void;
  isStopping: boolean;
  stopError: string | null;
}

export const EnvironmentLeaveGuardModal: FC<EnvironmentLeaveGuardModalProps> = ({
  isOpen,
  onStay,
  onStopAndLeave,
  isStopping,
  stopError,
}) => {
  if (!isOpen) return null;

  return (
    <div className="ui-dialog-backdrop is-open" style={{ zIndex: 9999 }}>
      <div
        aria-labelledby="leave-guard-title"
        aria-modal="true"
        className="ui-dialog"
        role="dialog"
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <span className="live-dot" style={{ backgroundColor: 'var(--lime, #22c55e)' }} />
          <h2 id="leave-guard-title" style={{ margin: 0, fontSize: '1.25rem', fontFamily: 'var(--font-display)' }}>
            Environment Still Running
          </h2>
        </div>

        <p style={{ fontSize: '0.875rem', color: 'var(--muted, #94a3b8)', lineHeight: 1.6, margin: '0 0 1rem' }}>
          Your CTF environment is currently active in the cluster.
          <br /><br />
          Please stop the environment before leaving to release your slot and avoid exhausting session time.
        </p>

        {stopError && (
          <div className="auth-alert auth-alert-error" style={{ marginBottom: '1rem' }}>
            <Icon name="info" size={16} />
            <span>{stopError}</span>
          </div>
        )}

        <div className="ui-dialog-actions" style={{ display: 'flex', gap: '0.75rem' }}>
          <Button
            disabled={isStopping}
            onClick={onStay}
            style={{ flex: 1 }}
            type="button"
            variant="secondary"
          >
            Stay
          </Button>
          <Button
            disabled={isStopping}
            loading={isStopping}
            onClick={onStopAndLeave}
            style={{ flex: 1 }}
            type="button"
            variant="danger"
          >
            Stop Environment
          </Button>
        </div>
      </div>
    </div>
  );
};
