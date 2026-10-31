import { useEffect, useState } from 'react';
import { useDesign } from '../DesignProvider';

export function useScenePreferences() {
  const { preset, theme, enable3d, motionIntensity } = useDesign();
  const [reducedMotion, setReducedMotion] = useState(() => (
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ));

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  const intensity = Number.isFinite(motionIntensity) ? Math.max(0, Math.min(1, motionIntensity)) : 0;
  const motion = enable3d && !reducedMotion && intensity > 0;

  return {
    depth: enable3d,
    motion,
    intensity,
    // Read the same palette as DesignProvider rather than racing its root-style effect.
    palette: theme === 'light' ? preset.light : preset.dark,
    mono: preset.fonts.mono,
    motionReason: !enable3d ? '3D disabled in Design Studio' : reducedMotion
      ? 'Reduced motion preference' : intensity === 0 ? 'Motion intensity is zero' : '',
  };
}
