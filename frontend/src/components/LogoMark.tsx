import { useDesign } from '../design-system/DesignProvider';
import { getLogoVariant, type LogoVariantId } from '../design-system/logoVariants';

type LogoMarkProps = {
  variantId?: LogoVariantId;
  size?: 'small' | 'medium' | 'large';
  className?: string;
};

export function LogoMark({ variantId, size = 'small', className = '' }: LogoMarkProps) {
  const { logoVariant } = useDesign();
  const id = variantId ?? logoVariant.id;
  const variant = getLogoVariant(id);
  const classes = `brand-mark logo-mark logo-mark-${id} logo-mark-${variant.mode} logo-mark-${size} ${className}`;

  return (
    <span aria-hidden="true" className={classes}>
      <svg fill="none" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
        {id === 'signal-core' ? <>
          <circle className="logo-secondary" cx="32" cy="32" r="22" />
          <g className="logo-bars">
            <path d="M13 43 20 38V24l-7 4.5V43ZM25 39l7-4.5V18l-7 4.5V39ZM37 35.5l7-4.5V12l-7 4.5v23.5Z" />
            <path d="M13 47h38" />
          </g>
        </> : null}
        {id === 'cyber-grid' ? <>
          <rect className="logo-frame" height="44" rx="9" width="44" x="10" y="10" />
          <path className="logo-grid" d="M17 22h30M17 32h30M17 42h30M27 17v30M37 17v30" />
          <path className="logo-core" d="m32 22 10 10-10 10-10-10 10-10Z" />
        </> : null}
        {id === 'egyptian-eye' ? <>
          <path className="logo-eye" d="M9 32c7-10 15-15 23-15s16 5 23 15c-7 10-15 15-23 15S16 42 9 32Z" />
          <circle className="logo-core-fill" cx="32" cy="32" r="6" />
          <path className="logo-secondary" d="M9 32 4 27M9 32l-5 5M46 19l9-6" />
        </> : null}
        {id === 'critical-signal' ? <>
          <path className="logo-alert" d="m32 7 24 47H8L32 7Z" />
          <path className="logo-core" d="M32 22v16M32 46h.01" />
          <circle className="logo-secondary" cx="32" cy="32" r="27" />
        </> : null}
        {id === 'cipher-orbit' ? <>
          <g className="logo-orbit">
            <ellipse className="logo-secondary" cx="32" cy="32" rx="25" ry="11" transform="rotate(-24 32 32)" />
            <ellipse className="logo-secondary" cx="32" cy="32" rx="25" ry="11" transform="rotate(36 32 32)" />
          </g>
          <path className="logo-core" d="m32 18 12 7v14l-12 7-12-7V25l12-7Z" />
          <circle className="logo-core-fill" cx="32" cy="32" r="4" />
        </> : null}
      </svg>
    </span>
  );
}
