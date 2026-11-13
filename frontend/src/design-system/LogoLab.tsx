import { LogoMark } from '../components/LogoMark';
import { Badge } from '../components/ui';
import { useDesign } from './DesignProvider';

export function LogoLab() {
  const { logoVariant, logoVariants, setLogoVariant } = useDesign();

  return (
    <div className="logo-lab">
      <div className="logo-lab-heading">
        <div>
          <span className="platform-card-kicker">Logo Lab</span>
          <strong>Choose your signal.</strong>
        </div>
        <Badge tone="lime">{logoVariant.mode}</Badge>
      </div>
      <p className="logo-lab-copy">Switch between static and animated marks. Your choice updates the interface logo and browser tab icon.</p>
      <div className="logo-lab-grid" role="list" aria-label="Logo variants">
        {logoVariants.map((variant) => (
          <button
            aria-pressed={variant.id === logoVariant.id}
            className={`logo-lab-option ${variant.id === logoVariant.id ? 'is-active' : ''}`}
            key={variant.id}
            onClick={() => setLogoVariant(variant.id)}
            type="button"
          >
            <LogoMark size="medium" variantId={variant.id} />
            <span><strong>{variant.name}</strong><small>{variant.mode}</small></span>
          </button>
        ))}
      </div>
    </div>
  );
}
