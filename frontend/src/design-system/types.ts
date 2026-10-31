import type { Theme } from '../data/mockData';

export type DesignPresetId =
  | 'cyberpunk-neon'
  | 'minimal-professional'
  | 'premium-dark'
  | 'glassmorphism'
  | 'brutalist-tech'
  | 'terminal-hacker'
  | 'editorial-modern'
  | 'futuristic-3d'
  | 'neo-brutalist-colorful'
  | 'monochrome-luxury'
  | 'retro-computing'
  | 'organic-digital'
  | 'dashboard-dense'
  | 'experimental-creative'
  | 'light-mode-technical'
  | 'futuristic-aurora'
  | 'tactical-operations'
  | 'soft-modern'
  | `custom-${string}`;

export type PresetCategory = 'Dark' | 'Light' | 'Experimental' | 'Operational';

export type Palette = {
  ink: string;
  inkSoft: string;
  panel: string;
  panelDeep: string;
  line: string;
  lineSoft: string;
  white: string;
  muted: string;
  mutedLight: string;
  lime: string;
  limeSoft: string;
  blue: string;
};

export type DesignPreset = {
  id: DesignPresetId;
  name: string;
  description: string;
  category: PresetCategory;
  tags: string[];
  fonts: { sans: string; display: string; mono: string };
  dark: Palette;
  light: Palette;
  tokens: {
    radius: string;
    radiusSmall: string;
    density: string;
    shadow: string;
    shadowColor: string;
    borderStyle: 'solid' | 'dashed' | 'double';
    surface: string;
    grid: string;
    headingWeight: string;
    fontScale: string;
    navWidth: string;
    tilt: string;
  };
};

export type DesignContextValue = {
  theme: Theme;
  preset: DesignPreset;
  presetId: DesignPresetId;
  presets: DesignPreset[];
  recentPresetIds: DesignPresetId[];
  favoritePresetIds: DesignPresetId[];
  motionIntensity: number;
  enable3d: boolean;
  setPreset: (id: DesignPresetId) => void;
  toggleFavorite: (id: DesignPresetId) => void;
  randomize: () => void;
  previousPreset: () => void;
  nextPreset: () => void;
  setMotionIntensity: (value: number) => void;
  setEnable3d: (value: boolean) => void;
  savePreferred: () => void;
  resetDesign: () => void;
  saveCustomPreset: (name: string) => void;
};
