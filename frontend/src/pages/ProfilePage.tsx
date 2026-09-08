import { useAuth } from '../contexts/AuthContext';

/**
 * ProfilePage — User profile view.
 * Minimal display of user information.
 */
export function ProfilePage() {
  const { user, logout } = useAuth();

  if (!user) return null;

  const createdDate = new Date(user.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="max-w-lg">
      <h1 className="font-serif text-3xl text-[var(--text)] mb-1">Profile</h1>
      <p className="text-[var(--text-muted)] text-sm mb-8">Your account details.</p>

      {/* Avatar + name */}
      <div className="flex items-center gap-4 mb-8">
        <div className="w-12 h-12 rounded-full bg-[var(--accent)] flex items-center justify-center text-lg text-[var(--bg)] font-serif">
          {user.username.charAt(0).toUpperCase()}
        </div>
        <div>
          <p className="text-[var(--text)] font-medium">{user.username}</p>
          <p className="text-[var(--text-faint)] text-sm">{user.email}</p>
        </div>
      </div>

      {/* Details */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded divide-y divide-[var(--border)]/50">
        <div className="flex justify-between px-4 py-3">
          <span className="text-[12px] text-[var(--text-faint)]">Username</span>
          <span className="text-[12px] text-[var(--text)] font-mono">{user.username}</span>
        </div>
        <div className="flex justify-between px-4 py-3">
          <span className="text-[12px] text-[var(--text-faint)]">Email</span>
          <span className="text-[12px] text-[var(--text)]">{user.email}</span>
        </div>
        <div className="flex justify-between px-4 py-3">
          <span className="text-[12px] text-[var(--text-faint)]">Status</span>
          <span className={`text-[12px] ${user.is_active ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>
            {user.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        <div className="flex justify-between px-4 py-3">
          <span className="text-[12px] text-[var(--text-faint)]">Member Since</span>
          <span className="text-[12px] text-[var(--text)]">{createdDate}</span>
        </div>
      </div>

      {/* Sign out */}
      <button
        onClick={logout}
        className="mt-6 text-[var(--danger)] text-sm hover:underline cursor-pointer"
      >
        Sign Out
      </button>
    </div>
  );
}
