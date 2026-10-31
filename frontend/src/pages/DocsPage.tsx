import { Icon } from '../components/Icon';
import { Card } from '../components/ui';

export function DocsPage() {
  const sections = [
    {
      title: 'Getting Started with MIRRAGE',
      content:
        'MIRRAGE provides isolated cybersecurity environments for hands-on adversarial learning and deception research. Each challenge runs on real infrastructure — no canned simulations, no synthetic sandboxes. Connect via OpenVPN to access the dedicated target network.',
      steps: [
        'Register or authenticate with your operator credentials or passwordless email OTP.',
        'Navigate to the VPN workspace to download your dedicated OpenVPN (.ovpn) client profile.',
        'Launch an isolated session pod to provision your private dual-container target machine.',
        'Investigate listening ports, uncover deception layers, and retrieve the flag.',
      ],
    },
    {
      title: 'OpenVPN Connection & Subnet Routing',
      content:
        'Download your OpenVPN profile from the VPN Workspace or Session Console. Import it into OpenVPN Connect (Windows/macOS) or run via terminal on Linux. Once connected, your machine will be assigned a static tunnel IP in the 10.8.0.0/24 subnet with direct routing into the Kubernetes cluster pod network (10.42.0.0/16).',
      steps: [
        'Windows: Open OpenVPN Connect -> Import Profile -> File -> select mirrage.ovpn -> Connect.',
        'Linux: Run sudo apt install openvpn && sudo openvpn --config mirrage.ovpn in an active terminal.',
        'macOS: Import into OpenVPN Connect or Tunnelblick and initiate connection.',
        'Verification: Verify your assigned IP is reported under the VPN telemetry widget on the dashboard.',
      ],
    },
    {
      title: 'Dual-Container Architecture & Deception Mechanics',
      content:
        'Every MIRRAGE session spins up an isolated Kubernetes Pod with two containers:\n1. Mirage Decoy (Port 22/80): A deceptive honeypot service pretending to be an authentic server. It logs operator keystrokes, provides misleading clues, and analyzes exploration patterns.\n2. CTF Core Target (Port 2222/internal): The genuine challenge environment hidden behind internal network pivoting and deception markers.',
    },
    {
      title: 'Session Lifecycle & Inactivity Reapers',
      content:
        'To ensure optimal cluster capacity across operators, sessions have a 30-minute inactivity limit and an absolute 90-minute maximum lifespan. You can extend an active session by +1 hour before it expires using the Session Console controls.',
    },
    {
      title: 'Rules of Engagement',
      content:
        'Do not attack cluster infrastructure outside your assigned 10.42.0.0/16 pod subnet. Do not share flags with other operators. Do not attempt Denial of Service against the platform gateway. Respect the boundaries of each challenge.',
    },
  ];

  return (
    <div className="platform-page docs-page">
      <div className="platform-page-header">
        <div>
          <span className="platform-eyebrow">06 / field guide</span>
          <h1>Documentation</h1>
          <p>Architecture, VPN configuration, deception telemetry, and range guidelines.</p>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '800px' }}>
        {sections.map((sec, idx) => (
          <Card key={idx} style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.75rem',
                color: 'var(--lime)',
                backgroundColor: 'var(--panel-deep)',
                padding: '0.2rem 0.5rem',
                borderRadius: 'var(--radius-small)',
                border: '1px solid var(--line)',
              }}>
                0{idx + 1}
              </span>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontFamily: 'var(--font-display)', color: 'var(--white)' }}>
                {sec.title}
              </h2>
            </div>

            <p style={{
              color: 'var(--muted)',
              fontSize: '0.875rem',
              lineHeight: 1.7,
              margin: '0 0 1rem',
              whiteSpace: 'pre-line',
            }}>
              {sec.content}
            </p>

            {sec.steps && (
              <ol style={{
                margin: 0,
                padding: '0.75rem 1rem',
                backgroundColor: 'var(--panel-deep)',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--line-soft, var(--line))',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
              }}>
                {sec.steps.map((step, sIdx) => (
                  <li key={sIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--muted-light)' }}>
                    <span style={{ color: 'var(--lime)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', marginTop: '0.1rem' }}>
                      {String(sIdx + 1).padStart(2, '0')}.
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        ))}
      </div>

      <div style={{ marginTop: '2.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--muted)', fontSize: '0.75rem' }}>
        <Icon name="shield" size={14} />
        <span>Observation enhances understanding. What you see is not what was built.</span>
      </div>
    </div>
  );
}
