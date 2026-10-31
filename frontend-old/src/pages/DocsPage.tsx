/**
 * DocsPage — Documentation / getting started guide.
 * Clean editorial layout with minimal content sections.
 */
export function DocsPage() {
  const sections = [
    {
      title: 'Getting Started',
      content: 'MIRRAGE provides isolated cybersecurity environments for hands-on learning. Each challenge runs on real infrastructure — no simulations, no sandboxes. Connect via VPN to access the target network.',
    },
    {
      title: 'VPN Setup',
      content: 'Download your OpenVPN profile from the dashboard. Import it into your VPN client (OpenVPN Connect, Tunnelblick, or the CLI). Once connected, you\'ll be assigned an IP in the 10.42.0.0/24 range.',
      steps: [
        'Navigate to VPN & Signal in the sidebar',
        'Download your .ovpn configuration file',
        'Import into your OpenVPN client',
        'Connect and verify your assigned IP',
      ],
    },
    {
      title: 'Challenges',
      content: 'Each challenge is a self-contained investigation. You\'ll receive a target IP and a brief. Find the flag (format: MIRRAGE{...}) and submit it to earn points.',
    },
    {
      title: 'Signal',
      content: 'Signal provides metadata about your VPN profile and connection. Download it from the dashboard to get announcements and environment updates.',
    },
    {
      title: 'Rules',
      content: 'Do not attack infrastructure outside your assigned environment. Do not share flags. Do not disrupt other participants\' sessions. Respect the boundaries of each challenge.',
    },
  ];

  return (
    <div className="max-w-2xl">
      <h1 className="font-serif text-3xl text-[var(--text)] mb-1">Documentation</h1>
      <p className="text-[var(--text-muted)] text-sm mb-10">Everything you need to get started.</p>

      <div className="space-y-10">
        {sections.map((section, i) => (
          <div key={i}>
            <h2 className="text-base font-medium text-[var(--text)] mb-3">{section.title}</h2>
            <p className="text-[var(--text-muted)] text-sm leading-relaxed">{section.content}</p>
            {section.steps && (
              <ol className="mt-4 space-y-2">
                {section.steps.map((step, j) => (
                  <li key={j} className="flex items-start gap-3 text-sm">
                    <span className="font-mono text-[10px] text-[var(--accent)] mt-0.5 shrink-0">
                      {String(j + 1).padStart(2, '0')}
                    </span>
                    <span className="text-[var(--text-muted)]">{step}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
