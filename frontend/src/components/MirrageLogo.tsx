interface MirrageLogoProps {
  className?: string;
  size?: number;
}

/**
 * Minimal geometric logo inspired by pyramid geometry, reflection, and optical illusion.
 * Two opposing triangular facets with an inverted reflection and negative space refraction.
 */
export function MirrageLogo({ className = '', size = 28 }: MirrageLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`inline-block transition-transform duration-700 group-hover:scale-105 ${className}`}
      aria-hidden="true"
    >
      {/* Top Pyramid Structure */}
      <polygon
        points="24,4 40,30 24,30"
        fill="url(#goldLightGrad)"
        opacity="0.95"
      />
      <polygon
        points="24,4 8,30 24,30"
        fill="url(#goldDarkGrad)"
        opacity="0.8"
      />
      {/* Subtle Apex Capstone */}
      <polygon
        points="24,4 28,11 20,11"
        fill="#f8e7c9"
        opacity="0.9"
      />

      {/* Optical Illusion Gap / Horizon Line */}
      <line
        x1="4"
        y1="32"
        x2="44"
        y2="32"
        stroke="var(--gold-muted)"
        strokeWidth="1"
        strokeOpacity="0.3"
        strokeDasharray="2 3"
      />

      {/* Inverted Mirage Reflection (Displaced & Fragmented) */}
      <polygon
        points="24,44 38,34 24,34"
        fill="url(#goldLightGrad)"
        opacity="0.35"
      />
      <polygon
        points="24,44 10,34 24,34"
        fill="url(#goldDarkGrad)"
        opacity="0.25"
      />

      {/* Gradients */}
      <defs>
        <linearGradient id="goldLightGrad" x1="24" y1="4" x2="40" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#e5c898" />
          <stop offset="1" stopColor="#b8963e" />
        </linearGradient>
        <linearGradient id="goldDarkGrad" x1="8" y1="30" x2="24" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8a6d2b" />
          <stop offset="1" stopColor="#5a431c" />
        </linearGradient>
      </defs>
    </svg>
  );
}
