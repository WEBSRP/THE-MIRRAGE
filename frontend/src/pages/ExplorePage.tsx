import { useState } from 'react';
import { SectionReveal } from '../components/SectionReveal';
import { Link } from 'react-router-dom';

interface ScanTarget {
  id: string;
  name: string;
  surveyedCoords: string;
  observedCoords: string;
  variance: string;
  description: string;
  status: string;
}

const scanTargets: ScanTarget[] = [
  {
    id: 'T-01',
    name: 'Apex Capstone Alignment',
    surveyedCoords: '29°58′45.0″N 31°08′03.0″E',
    observedCoords: '29°58′45.4″N 31°08′03.2″E',
    variance: '+0.4″ Displacement',
    description: 'Under solar noon, the capstone cast aligns with true astronomical north. However, infrared thermography indicates a secondary shadow angled 7° westward.',
    status: 'Optical Anomaly',
  },
  {
    id: 'T-02',
    name: 'Western Colonnade Perimeter',
    surveyedCoords: '29°58′38.2″N 31°07′58.1″E',
    observedCoords: '29°58′38.2″N 31°07′58.1″E',
    variance: '0.00 (Geometric Match)',
    description: 'Measurements match historical records down to 2 millimeters. Yet ground-penetrating radar shows the foundation stones continue downwards 18 meters past bedrock.',
    status: 'Sub-Bedrock Extension',
  },
  {
    id: 'T-03',
    name: 'Eastern Mirage Basin (Oasis)',
    surveyedCoords: '29°58′41.6″N 31°08′12.4″E',
    observedCoords: 'UNRESOLVED / NULL',
    variance: 'Total Perceptual Shift',
    description: 'Visual spectrum reflects full sky and monumental pyramid. Direct physical contact disperses the surface to reveal dry, parched limestone floor.',
    status: 'Mirage / Dispersed',
  },
];

export function ExplorePage() {
  const [selectedTarget, setSelectedTarget] = useState<ScanTarget>(scanTargets[0]);
  const [opticalFilter, setOpticalFilter] = useState<'visible' | 'thermal' | 'subsurface'>('visible');
  const [scanActive, setScanActive] = useState(false);

  const triggerScan = () => {
    setScanActive(true);
    setTimeout(() => setScanActive(false), 800);
  };

  return (
    <main className="min-h-screen bg-[var(--obsidian)] text-[var(--parchment)] pt-32 pb-24 px-6 sm:px-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <SectionReveal>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <span className="text-xs font-semibold tracking-[0.25em] text-[var(--gold-muted)] uppercase">
              Field Analysis Tool
            </span>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl text-[var(--sandstone-light)] tracking-wide mt-3 mb-6">
              EXPLORE THE ANOMALIES
            </h1>
            <p className="text-base sm:text-lg text-[var(--sandstone)]/80 leading-relaxed">
              Interactive structural triangulation tool. Compare surveyed physical architectural coordinates with observed optical phenomena.
            </p>
          </div>
        </SectionReveal>

        {/* Interactive Scanner Interface */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start mb-16">
          {/* Target Selector List */}
          <div className="lg:col-span-4 space-y-3">
            <h2 className="text-xs font-semibold tracking-widest text-[var(--gold-muted)] uppercase mb-4">
              SURVEY SECTORS
            </h2>
            {scanTargets.map((target) => (
              <button
                key={target.id}
                onClick={() => {
                  setSelectedTarget(target);
                  triggerScan();
                }}
                className={`w-full text-left p-5 border transition-all duration-300 ${
                  selectedTarget.id === target.id
                    ? 'border-[var(--gold-muted)] bg-[var(--dark-earth)]/60 text-[var(--sandstone-light)] shadow-lg'
                    : 'border-[var(--gold-muted)]/15 bg-[var(--dark-earth)]/20 text-[var(--sandstone)]/70 hover:border-[var(--gold-muted)]/40 hover:text-[var(--sandstone-light)]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-[var(--gold-muted)]">{target.id}</span>
                  <span className="text-[10px] px-2 py-0.5 border border-[var(--gold-muted)]/30 rounded text-[var(--gold-muted)] font-medium">
                    {target.status}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-[var(--sandstone-light)]">{target.name}</h3>
                <p className="text-xs text-[var(--sandstone)]/50 mt-1">{target.variance}</p>
              </button>
            ))}
          </div>

          {/* Analysis Viewport Display */}
          <div className="lg:col-span-8 border border-[var(--gold-muted)]/20 bg-[var(--dark-earth)]/30 p-6 sm:p-8 relative">
            {/* Viewport Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[var(--gold-muted)]/15 mb-6">
              <div>
                <span className="text-xs font-mono text-[var(--gold-muted)]">{selectedTarget.id} // OPTICAL SCANNER</span>
                <h3 className="text-xl font-semibold text-[var(--sandstone-light)] mt-1">{selectedTarget.name}</h3>
              </div>

              {/* Spectrum Mode Toggle */}
              <div className="flex items-center gap-2">
                {(['visible', 'thermal', 'subsurface'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => {
                      setOpticalFilter(mode);
                      triggerScan();
                    }}
                    className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border transition-all ${
                      opticalFilter === mode
                        ? 'border-[var(--gold-muted)] bg-[var(--gold-muted)]/20 text-[var(--gold-muted)] font-bold'
                        : 'border-[var(--gold-muted)]/10 text-[var(--sandstone)]/50 hover:text-[var(--sandstone-light)]'
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            {/* Simulated Radar / Coordinate Visualizer */}
            <div className="relative h-64 sm:h-80 w-full rounded border border-[var(--gold-muted)]/20 bg-[var(--obsidian)]/90 overflow-hidden flex items-center justify-center p-6 mb-6">
              {/* Grid Lines */}
              <div
                className="absolute inset-0 opacity-15"
                style={{
                  backgroundImage:
                    'linear-gradient(to right, var(--gold-muted) 1px, transparent 1px), linear-gradient(to bottom, var(--gold-muted) 1px, transparent 1px)',
                  backgroundSize: '32px 32px',
                }}
              />

              {/* Crosshairs & Scanning Animation */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-48 h-48 rounded-full border border-[var(--gold-muted)]/30 animate-pulse" />
                <div className="w-24 h-24 rounded-full border border-[var(--gold-muted)]/50" />
                <div className="absolute w-full h-px bg-[var(--gold-muted)]/20" />
                <div className="absolute h-full w-px bg-[var(--gold-muted)]/20" />
              </div>

              {/* Visual Mode Feedback */}
              <div className="relative z-10 text-center max-w-sm">
                <p className="text-xs font-mono text-[var(--gold-muted)] tracking-widest uppercase mb-2">
                  MODE: {opticalFilter.toUpperCase()} SPECTRUM
                </p>
                <p className="text-sm text-[var(--sandstone-light)] font-medium">
                  {opticalFilter === 'visible' && 'Displaying natural daylight reflection and perimeter shadow.'}
                  {opticalFilter === 'thermal' && 'Highlighting temperature gradient and subsurface heat dissipation.'}
                  {opticalFilter === 'subsurface' && 'Penetrating upper sandstone strata to detect hollow chambers.'}
                </p>
                {scanActive && (
                  <p className="text-xs text-[var(--gold-muted)] mt-2 font-mono animate-bounce">
                    RECALIBRATING OPTICS...
                  </p>
                )}
              </div>
            </div>

            {/* Coordinates Comparison Box */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono bg-[var(--obsidian)]/60 p-4 border border-[var(--gold-muted)]/15 mb-6">
              <div>
                <span className="text-[var(--sandstone)]/50 block">SURVEYED PERIMETER:</span>
                <span className="text-[var(--sandstone-light)] text-sm font-semibold">{selectedTarget.surveyedCoords}</span>
              </div>
              <div>
                <span className="text-[var(--gold-muted)]/70 block">OBSERVED OPTICAL BEAM:</span>
                <span className="text-[var(--gold-muted)] text-sm font-semibold">{selectedTarget.observedCoords}</span>
              </div>
            </div>

            {/* Findings Description */}
            <p className="text-sm text-[var(--sandstone)]/85 leading-relaxed">
              {selectedTarget.description}
            </p>
          </div>
        </div>

        {/* CTA banner */}
        <div className="p-8 sm:p-12 border border-[var(--gold-muted)]/20 bg-[var(--dark-earth)]/30 text-center">
          <h3 className="font-display text-2xl sm:text-3xl text-[var(--sandstone-light)] mb-4">
            READY TO INVESTIGATE FURTHER?
          </h3>
          <p className="text-sm sm:text-base text-[var(--sandstone)]/80 max-w-xl mx-auto mb-8 leading-relaxed">
            Direct access to the mirage environment allows active interaction with the survey endpoints.
          </p>
          <Link
            to="/enter"
            className="inline-flex items-center gap-3 px-8 py-4 bg-[var(--gold-muted)] hover:bg-[#c9a648] text-[var(--obsidian)] font-semibold text-xs tracking-widest uppercase transition-all shadow-xl"
          >
            ENTER THE MIRAGE →
          </Link>
        </div>
      </div>
    </main>
  );
}
