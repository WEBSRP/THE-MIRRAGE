export type LogoVariantId = 'signal-core' | 'cyber-grid' | 'egyptian-eye' | 'critical-signal' | 'cipher-orbit';

export type LogoVariant = {
  id: LogoVariantId;
  name: string;
  description: string;
  mode: 'static' | 'dynamic';
  tags: string[];
};

export const logoVariants: LogoVariant[] = [
  { id: 'signal-core', name: 'Signal Core', description: 'The original rising MIRRAGE signal.', mode: 'static', tags: ['Original', 'Signal'] },
  { id: 'cyber-grid', name: 'Cyber Grid', description: 'A spatial grid mark for technical operators.', mode: 'dynamic', tags: ['Cyber', 'Tech'] },
  { id: 'egyptian-eye', name: 'Egyptian Eye', description: 'An Egyptian-inspired eye for hidden knowledge.', mode: 'static', tags: ['Egyptian', 'Symbolic'] },
  { id: 'critical-signal', name: 'Critical Signal', description: 'An alert mark for high-priority observations.', mode: 'dynamic', tags: ['Critical', 'Alert'] },
  { id: 'cipher-orbit', name: 'Cipher Orbit', description: 'A coded core surrounded by moving telemetry.', mode: 'dynamic', tags: ['Cipher', 'Orbit'] },
];

export function isLogoVariantId(value: string | null): value is LogoVariantId {
  return Boolean(value && logoVariants.some((variant) => variant.id === value));
}

export function getLogoVariant(id: LogoVariantId): LogoVariant {
  return logoVariants.find((variant) => variant.id === id) ?? logoVariants[0];
}

type FaviconColors = { background: string; accent: string; secondary: string };

function faviconShape(id: LogoVariantId, accent: string, secondary: string) {
  switch (id) {
    case 'cyber-grid':
      return `<rect x="10" y="10" width="44" height="44" rx="9" fill="none" stroke="${secondary}" stroke-opacity=".45" stroke-width="2"/><path d="M17 22h30M17 32h30M17 42h30M27 17v30M37 17v30" stroke="${secondary}" stroke-opacity=".34" stroke-width="1.5"/><path d="M32 22 42 32 32 42 22 32Z" fill="none" stroke="${accent}" stroke-width="2.5"/>`;
    case 'egyptian-eye':
      return `<path d="M9 32c7-10 15-15 23-15s16 5 23 15c-7 10-15 15-23 15S16 42 9 32Z" fill="none" stroke="${accent}" stroke-linejoin="round" stroke-width="2.5"/><circle cx="32" cy="32" r="6" fill="${accent}"/><path d="M9 32 4 27M9 32l-5 5M46 19l9-6" fill="none" stroke="${secondary}" stroke-linecap="round" stroke-width="2"/>`;
    case 'critical-signal':
      return `<path d="m32 7 24 47H8L32 7Z" fill="none" stroke="${accent}" stroke-linejoin="round" stroke-width="2.5"/><path d="M32 22v16M32 46h.01" stroke="${accent}" stroke-linecap="round" stroke-width="3"/><circle cx="32" cy="32" r="27" fill="none" stroke="${secondary}" stroke-opacity=".35" stroke-width="1.5"/>`;
    case 'cipher-orbit':
      return `<ellipse cx="32" cy="32" rx="25" ry="11" fill="none" stroke="${secondary}" stroke-opacity=".42" stroke-width="1.5" transform="rotate(-24 32 32)"/><ellipse cx="32" cy="32" rx="25" ry="11" fill="none" stroke="${secondary}" stroke-opacity=".42" stroke-width="1.5" transform="rotate(36 32 32)"/><path d="m32 18 12 7v14l-12 7-12-7V25l12-7Z" fill="none" stroke="${accent}" stroke-linejoin="round" stroke-width="2.5"/><circle cx="32" cy="32" r="4" fill="${accent}"/>`;
    case 'signal-core':
    default:
      return `<circle cx="32" cy="32" r="22" fill="none" stroke="${secondary}" stroke-opacity=".32" stroke-width="1.5"/><path d="M13 43 20 38V24l-7 4.5v14.5ZM25 39l7-4.5V18l-7 4.5V39ZM37 35.5l7-4.5V12l-7 4.5v23.5Z" fill="none" stroke="${accent}" stroke-linejoin="round" stroke-width="2.5"/><path d="M13 47h38" stroke="${accent}" stroke-linecap="round" stroke-opacity=".55" stroke-width="1.5"/>`;
  }
}

export function createFaviconSvg(id: LogoVariantId, colors: FaviconColors) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="${colors.background}"/>${faviconShape(id, colors.accent, colors.secondary)}</svg>`;
}
