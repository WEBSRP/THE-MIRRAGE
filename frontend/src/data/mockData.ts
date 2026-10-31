export type Theme = 'dark' | 'light';

export type ChallengeCategory = 'Web' | 'Network' | 'Cloud' | 'Forensics' | 'Crypto' | 'Perception' | 'Deception' | 'Isolated Lab' | string;
export type Difficulty = 'Easy' | 'Medium' | 'Hard' | 'Expert';
export type ChallengeStatus = 'available' | 'solved';

export type MockUser = {
  id: string;
  name: string;
  username: string;
  email: string;
  role: string;
  createdAt: string;
  points: number;
  rank: number;
  avatar: string;
};

export type Challenge = {
  id: string;
  title: string;
  description: string;
  category: ChallengeCategory;
  difficulty: Difficulty;
  points: number;
  solveRate: number;
  estimatedTime: string;
  status: ChallengeStatus;
  flag: string;
  objectives: string[];
  hints: string[];
  tags: string[];
};

export type ActivityItem = {
  id: string;
  type: 'solve' | 'session' | 'vpn' | 'profile' | 'system';
  title: string;
  detail: string;
  timestamp: string;
  tone: 'lime' | 'blue' | 'orange' | 'muted';
};

export type SessionStatus = 'starting' | 'ready' | 'stopping' | 'stopped' | 'expired' | 'error';

export type MockSession = {
  id: string;
  title: string;
  target: string;
  category: ChallengeCategory;
  status: SessionStatus;
  ip: string;
  startedAt: string;
  expiresAt: number | null;
  progress: number;
  output: string[];
};

export type VpnStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export type MockVpn = {
  status: VpnStatus;
  server: string;
  ip: string | null;
  connectedAt: number | null;
  lastError: string | null;
  history: Array<{ id: string; event: string; detail: string; time: string; tone: 'lime' | 'orange' | 'muted' }>;
};

export type LeaderboardEntry = {
  rank: number;
  username: string;
  name: string;
  points: number;
  solved: number;
  change: number;
  isCurrentUser?: boolean;
};

export const DEMO_EMAIL = 'operator@mirrage.me';
export const DEMO_PASSWORD = 'observe';
export const DEMO_OTP = '424242';

export const mockUser: MockUser = {
  id: 'usr_001',
  name: 'Avery Chen',
  username: 'aetherline',
  email: DEMO_EMAIL,
  role: 'Field operator',
  createdAt: '2026-01-14',
  points: 1280,
  rank: 18,
  avatar: 'AC',
};

export const mockChallenges: Challenge[] = [
  {
    id: 'quiet-proxy',
    title: 'The Quiet Proxy',
    description: 'A low-noise service is forwarding requests somewhere it should not. Trace the boundary and find the header that changes everything.',
    category: 'Web',
    difficulty: 'Easy',
    points: 180,
    solveRate: 68,
    estimatedTime: '20 min',
    status: 'available',
    flag: 'MIRRAGE{proxy_headers_are_signals}',
    objectives: ['Map the request flow', 'Identify the hidden upstream', 'Extract the operator flag from the forwarded response'],
    hints: ['Start by comparing the response headers across two paths.', 'The proxy is quiet, not invisible.'],
    tags: ['HTTP', 'Recon', 'Headers'],
  },
  {
    id: 'ghost-subnet',
    title: 'Ghost in the Subnet',
    description: 'Something keeps answering on a subnet that appears empty. Use the available telemetry to locate the unlisted service.',
    category: 'Network',
    difficulty: 'Medium',
    points: 340,
    solveRate: 41,
    estimatedTime: '35 min',
    status: 'available',
    flag: 'MIRRAGE{listen_between_the_lines}',
    objectives: ['Profile the target subnet', 'Correlate the packet cadence', 'Reach the ghost service and recover its token'],
    hints: ['Silence is also a pattern.', 'The last octet is not random.'],
    tags: ['TCP', 'Subnetting', 'Enumeration'],
  },
  {
    id: 'glasshouse-protocol',
    title: 'Glasshouse Protocol',
    description: 'An exposed cloud workload is perfectly configured until it is observed. Find the permission boundary that turns the glasshouse opaque.',
    category: 'Cloud',
    difficulty: 'Hard',
    points: 520,
    solveRate: 19,
    estimatedTime: '55 min',
    status: 'available',
    flag: 'MIRRAGE{least_privilege_is_a_map}',
    objectives: ['Audit the workload identity', 'Trace the role assumption path', 'Read the secret without breaking the workload'],
    hints: ['The instance is not the principal you need.', 'Look for a role that was built for a different room.'],
    tags: ['IAM', 'Cloud', 'Privilege'],
  },
  {
    id: 'afterimage',
    title: 'Afterimage',
    description: 'A deleted file keeps leaving evidence in the telemetry stream. Reconstruct the timeline and identify what the operator tried to hide.',
    category: 'Forensics',
    difficulty: 'Medium',
    points: 290,
    solveRate: 37,
    estimatedTime: '40 min',
    status: 'available',
    flag: 'MIRRAGE{deleted_is_not_gone}',
    objectives: ['Build a timeline from the event stream', 'Locate the deleted artifact', 'Recover the original operator note'],
    hints: ['Timestamps tell you where to look, not what to trust.', 'The afterimage lives one layer below the file.'],
    tags: ['Timeline', 'Logs', 'Recovery'],
  },
  {
    id: 'paper-cipher',
    title: 'Paper Cipher',
    description: 'A small message has been folded into an ordinary-looking configuration. Decode the structure before the signal rotates.',
    category: 'Crypto',
    difficulty: 'Expert',
    points: 670,
    solveRate: 11,
    estimatedTime: '70 min',
    status: 'available',
    flag: 'MIRRAGE{the_key_was_in_plain_sight}',
    objectives: ['Identify the encoding layers', 'Recover the rotation key', 'Validate the decoded message against the signal'],
    hints: ['Do not start with the characters. Start with the shape.', 'The configuration comments are not comments.'],
    tags: ['Encoding', 'Analysis', 'Keys'],
  },
  {
    id: 'warm-cache',
    title: 'Warm Cache',
    description: 'A familiar dashboard leaks a little more state than it should. Find the cache boundary and prove what was left behind.',
    category: 'Web',
    difficulty: 'Easy',
    points: 150,
    solveRate: 74,
    estimatedTime: '15 min',
    status: 'available',
    flag: 'MIRRAGE{state_lingers_after_logout}',
    objectives: ['Inspect cache behavior', 'Compare anonymous and known responses', 'Recover the stale session marker'],
    hints: ['The page is not the only response.', 'Check what survives a logout.'],
    tags: ['Cache', 'Sessions', 'Web'],
  },
];

export const mockActivity: ActivityItem[] = [
  { id: 'act-1', type: 'solve', title: 'Challenge solved', detail: 'The Quiet Proxy · +180 pts', timestamp: '18 min ago', tone: 'lime' },
  { id: 'act-2', type: 'session', title: 'Session started', detail: 'Ghost in the Subnet · lab-04', timestamp: '42 min ago', tone: 'blue' },
  { id: 'act-3', type: 'vpn', title: 'VPN profile downloaded', detail: 'eu-west-02 · simulated', timestamp: '1 hr ago', tone: 'orange' },
  { id: 'act-4', type: 'system', title: 'Signal received', detail: 'Weekly range update', timestamp: 'Yesterday', tone: 'muted' },
];

export const mockSessions: MockSession[] = [
  {
    id: 'session-ghost-01',
    title: 'Ghost in the Subnet',
    target: 'ghost-subnet.lab',
    category: 'Network',
    status: 'ready',
    ip: '10.42.0.18',
    startedAt: 'Today, 09:42',
    expiresAt: Date.now() + 23 * 60 * 1000,
    progress: 100,
    output: ['MIRRAGE LAB CONSOLE / SIMULATED', 'Connecting to ghost-subnet.lab...', 'Target available at 10.42.0.18', 'Telemetry stream attached.', 'Ready for operator input.'],
  },
  {
    id: 'session-proxy-02',
    title: 'The Quiet Proxy',
    target: 'quiet-proxy.lab',
    category: 'Web',
    status: 'stopped',
    ip: '10.42.0.11',
    startedAt: 'Yesterday, 16:10',
    expiresAt: null,
    progress: 100,
    output: ['Session stopped by operator.', 'Artifacts retained in the activity log.'],
  },
];

export const mockVpn: MockVpn = {
  status: 'disconnected',
  server: 'eu-west-02.mirrage.test',
  ip: null,
  connectedAt: null,
  lastError: null,
  history: [
    { id: 'vpn-1', event: 'Profile downloaded', detail: 'eu-west-02', time: 'Today, 08:56', tone: 'lime' },
    { id: 'vpn-2', event: 'Disconnected', detail: 'Manual disconnect', time: 'Yesterday, 18:24', tone: 'muted' },
    { id: 'vpn-3', event: 'Connection error', detail: 'Simulated timeout', time: 'Yesterday, 18:20', tone: 'orange' },
  ],
};

export const mockLeaderboard: LeaderboardEntry[] = [
  { rank: 1, username: 'nullroute', name: 'N. Route', points: 4820, solved: 18, change: 0 },
  { rank: 2, username: 'packetmason', name: 'P. Mason', points: 4140, solved: 15, change: 2 },
  { rank: 3, username: 'cipherbird', name: 'C. Bird', points: 3920, solved: 14, change: -1 },
  { rank: 4, username: 'lowandslow', name: 'L. Slow', points: 3510, solved: 12, change: 1 },
  { rank: 5, username: 'echochamber', name: 'E. Chamber', points: 3240, solved: 11, change: -2 },
  { rank: 18, username: mockUser.username, name: mockUser.name, points: mockUser.points, solved: 4, change: 3, isCurrentUser: true },
];

export const categoryOptions: ChallengeCategory[] = ['Web', 'Network', 'Cloud', 'Forensics', 'Crypto'];
export const difficultyOptions: Difficulty[] = ['Easy', 'Medium', 'Hard', 'Expert'];

export function getChallenge(id: string): Challenge | undefined {
  return mockChallenges.find((challenge) => challenge.id === id);
}
