import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useTheme } from '../state/AppState';
import { defaultPresets, getPreset } from './presets';
import { createFaviconSvg, getLogoVariant, isLogoVariantId, logoVariants, type LogoVariantId } from './logoVariants';
import type { DesignContextValue, DesignPreset, DesignPresetId } from './types';

const DesignContext = createContext<DesignContextValue | null>(null);
const PRESET_KEY = 'mirrage-design-preset';
const PREFERRED_KEY = 'mirrage-design-preferred';
const FAVORITES_KEY = 'mirrage-design-favorites';
const RECENT_KEY = 'mirrage-design-recent';
const CUSTOM_KEY = 'mirrage-design-custom';
const LOGO_KEY = 'mirrage-logo-variant';

function readJson<T>(key: string, fallback: T): T {
  try {
    const value = window.localStorage.getItem(key);
    return value ? JSON.parse(value) as T : fallback;
  } catch {
    return fallback;
  }
}

export function DesignProvider({ children }: { children: ReactNode }) {
  const { theme } = useTheme();
  const [customPresets, setCustomPresets] = useState<DesignPreset[]>(() => readJson<DesignPreset[]>(CUSTOM_KEY, []));
  const allPresets = useMemo(() => [...defaultPresets, ...customPresets], [customPresets]);
  const [presetId, setPresetId] = useState<DesignPresetId>(() => {
    const stored = window.localStorage.getItem(PRESET_KEY) as DesignPresetId | null;
    const preferred = window.localStorage.getItem(PREFERRED_KEY) as DesignPresetId | null;
    return stored ?? preferred ?? 'cyberpunk-neon';
  });
  const [favoritePresetIds, setFavoritePresetIds] = useState<DesignPresetId[]>(() => readJson<DesignPresetId[]>(FAVORITES_KEY, []));
  const [recentPresetIds, setRecentPresetIds] = useState<DesignPresetId[]>(() => readJson<DesignPresetId[]>(RECENT_KEY, []));
  const [motionIntensity, setMotionIntensityState] = useState(() => Number(window.localStorage.getItem('mirrage-design-motion') ?? '1'));
  const [enable3d, setEnable3dState] = useState(() => window.localStorage.getItem('mirrage-design-3d') !== 'false');
  const [logoVariantId, setLogoVariantId] = useState<LogoVariantId>(() => {
    const stored = window.localStorage.getItem(LOGO_KEY);
    return isLogoVariantId(stored) ? stored : 'signal-core';
  });
  const preset = getPreset(presetId, allPresets);
  const logoVariant = getLogoVariant(logoVariantId);

  useEffect(() => {
    if (!allPresets.some((item) => item.id === presetId)) setPresetId('cyberpunk-neon');
  }, [allPresets, presetId]);

  useEffect(() => {
    const root = document.documentElement;
    const palette = theme === 'light' ? preset.light : preset.dark;
    const properties: Record<string, string> = {
      '--ink': palette.ink, '--ink-soft': palette.inkSoft, '--panel': palette.panel, '--panel-deep': palette.panelDeep,
      '--line': palette.line, '--line-soft': palette.lineSoft, '--white': palette.white, '--muted': palette.muted,
      '--muted-light': palette.mutedLight, '--lime': palette.lime, '--lime-soft': palette.limeSoft, '--blue': palette.blue,
      '--design-font': preset.fonts.sans, '--design-display-font': preset.fonts.display, '--design-mono': preset.fonts.mono,
      '--sans': preset.fonts.sans, '--mono': preset.fonts.mono,
      '--design-radius': preset.tokens.radius, '--design-radius-small': preset.tokens.radiusSmall, '--design-density': preset.tokens.density,
      '--design-shadow': preset.tokens.shadow, '--design-shadow-color': preset.tokens.shadowColor, '--design-border-style': preset.tokens.borderStyle,
      '--design-surface': preset.tokens.surface, '--design-grid-opacity': preset.tokens.grid, '--design-heading-weight': preset.tokens.headingWeight,
      '--design-font-scale': preset.tokens.fontScale, '--design-nav-width': preset.tokens.navWidth, '--design-tilt': preset.tokens.tilt,
      '--design-motion': String(motionIntensity), '--design-depth': enable3d ? '1' : '0',
    };
    Object.entries(properties).forEach(([key, value]) => root.style.setProperty(key, value));
    root.dataset.preset = preset.id;
    root.dataset.motion = motionIntensity === 0 ? 'off' : motionIntensity < .65 ? 'low' : 'full';
    root.dataset.depth = enable3d ? 'on' : 'off';
  }, [enable3d, motionIntensity, preset, theme]);

  useEffect(() => { window.localStorage.setItem(PRESET_KEY, presetId); }, [presetId]);
  useEffect(() => { window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(favoritePresetIds)); }, [favoritePresetIds]);
  useEffect(() => { window.localStorage.setItem(RECENT_KEY, JSON.stringify(recentPresetIds)); }, [recentPresetIds]);
  useEffect(() => { window.localStorage.setItem(CUSTOM_KEY, JSON.stringify(customPresets)); }, [customPresets]);
  useEffect(() => { window.localStorage.setItem('mirrage-design-motion', String(motionIntensity)); }, [motionIntensity]);
  useEffect(() => { window.localStorage.setItem('mirrage-design-3d', String(enable3d)); }, [enable3d]);
  useEffect(() => { window.localStorage.setItem(LOGO_KEY, logoVariantId); }, [logoVariantId]);

  useEffect(() => {
    const palette = theme === 'light' ? preset.light : preset.dark;
    const href = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(createFaviconSvg(logoVariantId, { background: palette.ink, accent: palette.lime, secondary: palette.blue }))}`;
    const links = document.querySelectorAll<HTMLLinkElement>('link[rel~="icon"]');
    links.forEach((link) => { link.href = href; });
    document.documentElement.dataset.logo = logoVariantId;
  }, [logoVariantId, preset, theme]);

  const setPreset = useCallback((id: DesignPresetId) => {
    if (!allPresets.some((item) => item.id === id)) return;
    setPresetId(id);
    setRecentPresetIds((current) => [id, ...current.filter((item) => item !== id)].slice(0, 6));
  }, [allPresets]);
  const toggleFavorite = useCallback((id: DesignPresetId) => setFavoritePresetIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]), []);
  const randomize = useCallback(() => { const choices = allPresets.filter((item) => item.id !== presetId); const next = choices[Math.floor(Math.random() * choices.length)]; if (next) setPreset(next.id); setMotionIntensityState(Math.round(Math.random() * 20) / 20); setEnable3dState(Math.random() > .18); }, [allPresets, presetId, setPreset]);
  const move = useCallback((delta: number) => { const index = allPresets.findIndex((item) => item.id === presetId); const next = allPresets[(index + delta + allPresets.length) % allPresets.length]; if (next) setPreset(next.id); }, [allPresets, presetId, setPreset]);
  const previousPreset = useCallback(() => move(-1), [move]);
  const nextPreset = useCallback(() => move(1), [move]);
  const setMotionIntensity = useCallback((value: number) => setMotionIntensityState(Math.max(0, Math.min(1, value))), []);
  const setEnable3d = useCallback((value: boolean) => setEnable3dState(value), []);
  const setLogoVariant = useCallback((id: LogoVariantId) => {
    if (logoVariants.some((variant) => variant.id === id)) setLogoVariantId(id);
  }, []);
  const savePreferred = useCallback(() => window.localStorage.setItem(PREFERRED_KEY, presetId), [presetId]);
  const resetDesign = useCallback(() => { setPreset('cyberpunk-neon'); setMotionIntensityState(1); setEnable3dState(true); setLogoVariantId('signal-core'); }, [setPreset]);
  const saveCustomPreset = useCallback((name: string) => {
    const cleanName = name.trim();
    if (!cleanName) return;
    const custom: DesignPreset = { ...preset, id: `custom-${Date.now()}`, name: cleanName, description: `Custom variation based on ${preset.name}.`, category: 'Experimental', tags: ['Custom', ...preset.tags.slice(0, 2)], dark: { ...preset.dark }, light: { ...preset.light }, tokens: { ...preset.tokens }, fonts: { ...preset.fonts } };
    setCustomPresets((current) => [...current, custom]);
    setPreset(custom.id);
  }, [preset, setPreset]);

  const value = useMemo<DesignContextValue>(() => ({ theme, preset, presetId, presets: allPresets, recentPresetIds, favoritePresetIds, motionIntensity, enable3d, setPreset, toggleFavorite, randomize, previousPreset, nextPreset, setMotionIntensity, setEnable3d, savePreferred, resetDesign, saveCustomPreset, logoVariant, logoVariants, setLogoVariant }), [allPresets, enable3d, favoritePresetIds, logoVariant, motionIntensity, nextPreset, preset, presetId, previousPreset, randomize, recentPresetIds, resetDesign, saveCustomPreset, savePreferred, setEnable3d, setLogoVariant, setMotionIntensity, setPreset, theme, toggleFavorite]);
  return <DesignContext.Provider value={value}>{children}</DesignContext.Provider>;
}

export function useDesign() {
  const context = useContext(DesignContext);
  if (!context) throw new Error('useDesign must be used inside DesignProvider');
  return context;
}
