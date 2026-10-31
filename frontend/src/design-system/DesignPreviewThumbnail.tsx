import type { CSSProperties } from 'react';
import type { DesignPreset } from './types';

export function DesignPreviewThumbnail({ preset, active = false }: { preset: DesignPreset; active?: boolean }) {
  return <div className={`design-thumb design-thumb-${preset.id} ${active ? 'is-active' : ''}`} style={{ '--thumb-accent': preset.dark.lime, '--thumb-bg': preset.dark.ink, '--thumb-panel': preset.dark.panel, '--thumb-line': preset.dark.line } as CSSProperties}><span className="design-thumb-top"><i /><i /><i /></span><span className="design-thumb-sidebar" /><span className="design-thumb-main"><i /><i /><i /><i /></span><span className="design-thumb-orb" /><span className="design-thumb-label">{preset.name.slice(0, 3).toUpperCase()}</span></div>;
}
