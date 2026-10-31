/**
 * MonolithIllustration — A geometric monolith/gateway structure
 * matching the reference: tall rectangular form with a golden
 * doorway/portal, reflected in water, against a starfield sky.
 * Used on the landing page hero section.
 */
export function MonolithIllustration({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 400 500"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Sky gradient */}
      <defs>
        <linearGradient id="sky-grad" x1="200" y1="0" x2="200" y2="260" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0B0D0F" />
          <stop offset="0.5" stopColor="#111417" />
          <stop offset="1" stopColor="#1a1d22" />
        </linearGradient>
        <linearGradient id="water-grad" x1="200" y1="260" x2="200" y2="500" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#15191D" />
          <stop offset="1" stopColor="#0B0D0F" />
        </linearGradient>
        <linearGradient id="monolith-grad" x1="200" y1="60" x2="200" y2="260" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#252A2E" />
          <stop offset="1" stopColor="#1a1d22" />
        </linearGradient>
        <linearGradient id="glow" x1="200" y1="100" x2="200" y2="260" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#C49A52" stopOpacity="0.6" />
          <stop offset="1" stopColor="#C49A52" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="reflection-grad" x1="200" y1="260" x2="200" y2="420" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#252A2E" stopOpacity="0.4" />
          <stop offset="1" stopColor="#0B0D0F" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Sky */}
      <rect width="400" height="260" fill="url(#sky-grad)" />

      {/* Stars */}
      {[
        [45, 30], [120, 50], [280, 25], [350, 60], [90, 100],
        [310, 90], [60, 150], [340, 140], [200, 20], [150, 130],
        [250, 110], [30, 200], [370, 180], [170, 70], [230, 40],
      ].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.2 : 0.7} fill="#E8E5DE" opacity={0.3 + (i % 4) * 0.15} />
      ))}

      {/* Moon */}
      <circle cx="310" cy="60" r="12" fill="#E8E5DE" opacity="0.9" />
      <circle cx="310" cy="60" r="14" fill="none" stroke="#E8E5DE" strokeWidth="0.5" opacity="0.2" />

      {/* Water */}
      <rect y="260" width="400" height="240" fill="url(#water-grad)" />

      {/* Horizon line */}
      <line x1="0" y1="260" x2="400" y2="260" stroke="#C49A52" strokeWidth="0.5" opacity="0.3" />

      {/* Monolith body */}
      <rect x="160" y="60" width="80" height="200" fill="url(#monolith-grad)" stroke="#2a2f35" strokeWidth="0.5" />

      {/* Gateway/doorway */}
      <rect x="180" y="160" width="40" height="100" fill="#0B0D0F" />
      <rect x="180" y="160" width="40" height="100" fill="url(#glow)" opacity="0.4" />

      {/* Doorway frame — thin amber lines */}
      <line x1="180" y1="160" x2="180" y2="260" stroke="#C49A52" strokeWidth="0.8" opacity="0.6" />
      <line x1="220" y1="160" x2="220" y2="260" stroke="#C49A52" strokeWidth="0.8" opacity="0.6" />
      <line x1="180" y1="160" x2="220" y2="160" stroke="#C49A52" strokeWidth="0.8" opacity="0.6" />

      {/* Top accent */}
      <line x1="160" y1="60" x2="240" y2="60" stroke="#C49A52" strokeWidth="1" opacity="0.5" />

      {/* Ambient glow from doorway */}
      <ellipse cx="200" cy="260" rx="60" ry="8" fill="#C49A52" opacity="0.08" />

      {/* Reflection (mirrored, faded) */}
      <g opacity="0.25" transform="translate(0, 520) scale(1, -1)">
        <rect x="160" y="60" width="80" height="200" fill="url(#reflection-grad)" />
        <rect x="180" y="160" width="40" height="100" fill="#C49A52" opacity="0.1" />
      </g>

      {/* Water ripple lines */}
      {[275, 300, 330, 365, 405].map((y, i) => (
        <line
          key={i}
          x1={120 + i * 10}
          y1={y}
          x2={280 - i * 10}
          y2={y}
          stroke="#C49A52"
          strokeWidth="0.3"
          opacity={0.15 - i * 0.025}
        />
      ))}
    </svg>
  );
}

/**
 * GatewayIllustration — A smaller geometric gateway/arch
 * Used on auth pages (login/register) as atmospheric decoration.
 */
export function GatewayIllustration({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 300"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="gate-grad" x1="100" y1="20" x2="100" y2="280" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#252A2E" />
          <stop offset="1" stopColor="#15191D" />
        </linearGradient>
      </defs>

      {/* Main structure */}
      <rect x="60" y="40" width="80" height="240" fill="url(#gate-grad)" stroke="#2a2f35" strokeWidth="0.5" />

      {/* Portal opening */}
      <rect x="78" y="140" width="44" height="140" fill="#0B0D0F" />

      {/* Portal glow */}
      <rect x="78" y="140" width="44" height="140" fill="#C49A52" opacity="0.05" />

      {/* Frame lines */}
      <line x1="78" y1="140" x2="78" y2="280" stroke="#C49A52" strokeWidth="0.6" opacity="0.4" />
      <line x1="122" y1="140" x2="122" y2="280" stroke="#C49A52" strokeWidth="0.6" opacity="0.4" />
      <line x1="78" y1="140" x2="122" y2="140" stroke="#C49A52" strokeWidth="0.6" opacity="0.4" />

      {/* Top cap */}
      <line x1="60" y1="40" x2="140" y2="40" stroke="#C49A52" strokeWidth="0.8" opacity="0.3" />

      {/* Decorative marks */}
      <line x1="55" y1="40" x2="55" y2="50" stroke="#C49A52" strokeWidth="0.5" opacity="0.2" />
      <line x1="145" y1="40" x2="145" y2="50" stroke="#C49A52" strokeWidth="0.5" opacity="0.2" />
    </svg>
  );
}

/**
 * TowerIllustration — A tall narrow structure
 * Used on the challenges detail page or sidebar decoration.
 */
export function TowerIllustration({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 400"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="tower-grad" x1="60" y1="0" x2="60" y2="400" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#252A2E" />
          <stop offset="0.8" stopColor="#15191D" />
          <stop offset="1" stopColor="#111417" />
        </linearGradient>
      </defs>

      {/* Tower body — tapered */}
      <polygon
        points="40,400 30,80 60,10 90,80 80,400"
        fill="url(#tower-grad)"
        stroke="#2a2f35"
        strokeWidth="0.5"
      />

      {/* Accent line at top */}
      <line x1="30" y1="80" x2="90" y2="80" stroke="#C49A52" strokeWidth="0.5" opacity="0.3" />

      {/* Window slits */}
      {[120, 180, 240, 300, 350].map((y, i) => (
        <rect
          key={i}
          x={55 - i * 0.5}
          y={y}
          width="2"
          height="12"
          fill="#C49A52"
          opacity={0.2 - i * 0.02}
        />
      ))}
    </svg>
  );
}
