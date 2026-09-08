import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { getVpnStatus, downloadVpnConfig, downloadSignalConfig, type VpnStatus } from '../services/vpnService';
import { getSessionStatus, type SessionStatusResponse } from '../services/sessionService';
import { getActivity, type ActivityLog } from '../services/activityService';
import { StartPlayingModal } from '../components/StartPlayingModal';

export function DashboardPage() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();
  
  const [vpnStatus, setVpnStatus] = useState<VpnStatus | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatusResponse | null>(null);
  const [activities, setActivities] = useState<ActivityLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const [vpnRes, sessionRes, activityRes] = await Promise.all([
          getVpnStatus().catch(() => null),
          getSessionStatus().catch(() => null),
          getActivity().catch(() => [])
        ]);

        if (mounted) {
          setVpnStatus(vpnRes);
          setSessionStatus(sessionRes);
          setActivities(activityRes || []);
          setIsLoading(false);
        }
      } catch {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      mounted = false;
    };
  }, []);

  const handleDownloadVpn = async () => {
    try {
      await downloadVpnConfig();
    } catch (error) {
      console.error('Failed to download VPN config', error);
    }
  };

  const handleDownloadSignal = async () => {
    try {
      await downloadSignalConfig();
    } catch (error) {
      console.error('Failed to download Signal config', error);
    }
  };

  const greeting = theme === 'morning' ? 'Good morning' : 'Good evening';
  
  // Environment ID generation or placeholder
  const envId = sessionStatus?.session_id 
    ? `MIRAGE-${sessionStatus.session_id.substring(0, 4).toUpperCase()}`
    : 'MIRAGE-7F31';
    
  const envIp = sessionStatus?.mirage_ip || '10.42.0.17';
  
  const isSessionOnline = sessionStatus?.status === 'active' || sessionStatus?.status === 'running';

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl text-[var(--text)]">
          {greeting}, {user?.username || 'Explorer'}.
        </h1>
        <p className="text-[var(--text-muted)] text-sm">
          Ready to uncover what lies beneath?
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Environment Status Card */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5 flex flex-col gap-4 lg:col-span-2">
          <div className="flex justify-between items-start">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
                YOUR ENVIRONMENT
              </span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-lg text-[var(--text)]">{envId}</span>
                {isSessionOnline ? (
                  <span className="text-[var(--success)] text-xs flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)] inline-block"></span>
                    Online
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)] text-xs flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] inline-block"></span>
                    Offline
                  </span>
                )}
              </div>
              <span className="font-mono text-sm text-[var(--text-muted)]">
                {envIp}
              </span>
            </div>
            
            <div className="flex flex-col items-end gap-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[var(--text-muted)]">VPN:</span>
                <span className={vpnStatus?.is_connected ? 'text-[var(--success)]' : 'text-[var(--text)]'}>
                  {vpnStatus?.is_connected ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[var(--text-muted)]">Signal:</span>
                <span className="text-[var(--text)]">Available</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 mt-2">
            {!isSessionOnline && (
              <button 
                onClick={() => setModalOpen(true)}
                className="px-3 py-1.5 bg-[var(--accent)] text-[#000000] rounded text-xs font-medium hover:opacity-90 transition-opacity"
              >
                Start Environment
              </button>
            )}
            <button 
              onClick={handleDownloadVpn}
              className="px-3 py-1.5 border border-[var(--border)] text-[var(--text)] rounded text-xs font-medium hover:bg-[var(--surface)] transition-colors"
            >
              Download VPN
            </button>
            <button 
              onClick={handleDownloadSignal}
              className="px-3 py-1.5 border border-[var(--border)] text-[var(--text)] rounded text-xs font-medium hover:bg-[var(--surface)] transition-colors"
            >
              Download Signal
            </button>
          </div>
        </div>

        <StartPlayingModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          onConfirm={() => navigate('/session')}
        />

        {/* Explore Challenges Card */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-5 flex flex-col justify-between gap-4">
          <div className="flex flex-col gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
              TRAINING
            </span>
            <p className="text-sm text-[var(--text)]">
              Step into realistic scenarios and test your skills.
            </p>
          </div>
          <Link 
            to="/challenges"
            className="text-[var(--accent)] text-sm hover:underline flex items-center gap-1 w-fit"
          >
            View Challenges →
          </Link>
        </div>
      </div>

      {/* Recent Activity Section */}
      <section className="flex flex-col gap-4">
        <h2 className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
          RECENT ACTIVITY
        </h2>
        
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded p-1">
          {isLoading ? (
            <div className="p-4 text-sm text-[var(--text-muted)] text-center">Loading activity...</div>
          ) : activities.length > 0 ? (
            <ul className="flex flex-col">
              {activities.map((activity, idx) => {
                const date = new Date(activity.timestamp);
                const isPositive = activity.event_type === 'challenge_solve' || activity.event_type === 'flag_submit';
                const details = activity.payload ? JSON.stringify(activity.payload) : '';
                
                return (
                  <li 
                    key={activity.id || idx}
                    className={`flex items-start gap-4 p-3 ${idx !== activities.length - 1 ? 'border-b border-[var(--border)]' : ''}`}
                  >
                    <span className="font-mono text-[11px] text-[var(--text-faint)] pt-0.5 whitespace-nowrap w-12">
                      {date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                    </span>
                    <div className="flex items-center pt-1.5">
                      <span className={`w-2 h-2 rounded-full ${isPositive ? 'bg-[var(--success)]' : 'bg-[var(--accent)]'}`}></span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-sm text-[var(--text)]">{activity.summary || activity.event_type || 'Unknown activity'}</span>
                      {details && details !== '{}' && (
                        <span className="text-xs text-[var(--text-muted)] mt-0.5 truncate max-w-sm">{details}</span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="p-8 text-sm text-[var(--text-muted)] text-center flex flex-col items-center gap-2">
              <span className="font-mono text-xs opacity-50">NO ACTIVITY</span>
              <p>Your recent actions will appear here.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
