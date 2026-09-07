import { useState } from 'react';
import { Link } from 'react-router-dom';
import { InteractiveOasisHero } from '../components/InteractiveOasisHero';
import { SectionReveal } from '../components/SectionReveal';

/* ─── Archive records data with subtle narrative anomalies ─── */
const archiveEntries = [
  {
    id: '001',
    title: 'Foundation Survey',
    date: '1923.03.14',
    classification: 'OPEN',
    excerpt:
      'Initial triangulation of the western perimeter stones. All measurements correspond precisely to known dynastic blueprints. Baseline survey established.',
    status: 'Verified',
  },
  {
    id: '002',
    title: 'Ambient Observation',
    date: '1923.06.02',
    classification: 'OPEN',
    excerpt:
      'Field notes from the second expedition. Ambient temperature variance and atmospheric refraction patterns logged at solar noon. No structural deviations reported.',
    status: 'Verified',
  },
  {
    id: '003',
    title: 'Reflection Discrepancy',
    date: '1924.11.08',
    classification: 'RESTRICTED',
    excerpt:
      'A secondary survey reported an angle anomaly in the northern stone facings. Under specific lighting, coordinates shifted by 14 meters. Flagged for internal review.',
    status: 'Amended',
  },
  {
    id: '007',
    // Deliberate numbering skip from 003 to 007
    title: 'Sub-Stratum Seal',
    date: '1925.██.██',
    classification: 'SEALED',
    excerpt:
      'Everything here has been preserved exactly as it was found. The subterranean threshold was sealed from within. Exterior masonry shows zero tool incisions.',
    status: 'Pending Review',
  },
];

export function HomePage() {
  const [expandedArchive, setExpandedArchive] = useState<string | null>(null);

  return (
    <main className="w-full bg-[var(--obsidian)] text-[var(--parchment)] overflow-hidden">
      {/* ═══════════════════════════════════════════════════════════════
          HERO: Photorealistic Daytime Desert & Interactive Oasis
         ═══════════════════════════════════════════════════════════════ */}
      <InteractiveOasisHero />

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 1: THE MIRRAGE PROJECT
         ═══════════════════════════════════════════════════════════════ */}
      <section className="relative py-28 lg:py-36 px-6 sm:px-8 border-b border-[var(--gold-muted)]/10">
        <div className="max-w-4xl mx-auto text-center">
          <SectionReveal>
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[var(--gold-muted)]/10 border border-[var(--gold-muted)]/20 mb-6">
              <span className="text-xs font-semibold tracking-[0.25em] text-[var(--gold-muted)] uppercase">
                Core Initiative
              </span>
            </div>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-wide text-[var(--sandstone-light)] mb-8">
              THE MIRRAGE PROJECT
            </h2>
          </SectionReveal>

          <SectionReveal delay={200}>
            <p className="text-lg sm:text-xl text-[var(--sandstone)]/85 leading-relaxed font-normal max-w-3xl mx-auto">
              An exploration of perception, architecture, and the boundaries between
              what is real and what appears to be real.
            </p>
          </SectionReveal>

          <SectionReveal delay={400}>
            <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6 text-left pt-8 border-t border-[var(--gold-muted)]/15">
              <div className="p-6 bg-[var(--dark-earth)]/30 border border-[var(--gold-muted)]/15">
                <span className="text-xs text-[var(--gold-muted)] font-mono">01. GEOMETRY</span>
                <h3 className="text-base font-semibold text-[var(--sandstone-light)] mt-2 mb-2">
                  Structural Deception
                </h3>
                <p className="text-sm text-[var(--sandstone)]/75 leading-relaxed">
                  Monumental architecture engineered to redirect gaze, deceive measurements, and protect hidden thresholds.
                </p>
              </div>

              <div className="p-6 bg-[var(--dark-earth)]/30 border border-[var(--gold-muted)]/15">
                <span className="text-xs text-[var(--gold-muted)] font-mono">02. OPTICS</span>
                <h3 className="text-base font-semibold text-[var(--sandstone-light)] mt-2 mb-2">
                  Perceptual Mirages
                </h3>
                <p className="text-sm text-[var(--sandstone)]/75 leading-relaxed">
                  Atmospheric heat layers and deliberate reflections creating convincing illusions of presence and absence.
                </p>
              </div>

              <div className="p-6 bg-[var(--dark-earth)]/30 border border-[var(--gold-muted)]/15">
                <span className="text-xs text-[var(--gold-muted)] font-mono">03. ARCHIVES</span>
                <h3 className="text-base font-semibold text-[var(--sandstone-light)] mt-2 mb-2">
                  Unaltered Records
                </h3>
                <p className="text-sm text-[var(--sandstone)]/75 leading-relaxed">
                  Field observations preserved without alteration, allowing anomalies to emerge through careful inspection.
                </p>
              </div>
            </div>
          </SectionReveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 2: THE DESERT REMEMBERS
         ═══════════════════════════════════════════════════════════════ */}
      <section className="relative py-32 lg:py-40 px-6 sm:px-8 overflow-hidden bg-cover bg-center" style={{ backgroundImage: "url('/images/archive_bg.jpg')" }}>
        {/* Darkening overlay */}
        <div className="absolute inset-0 bg-[var(--obsidian)]/85 backdrop-blur-[2px]" />

        <div className="relative z-10 max-w-4xl mx-auto text-center">
          <SectionReveal>
            <span className="text-xs tracking-[0.25em] text-[var(--gold-muted)]/80 uppercase font-medium">
              Archaeological Principle
            </span>
            <h2 className="font-display text-3xl sm:text-5xl lg:text-6xl tracking-wide text-[var(--sandstone-light)] mt-4 mb-8">
              THE DESERT REMEMBERS
            </h2>
          </SectionReveal>

          <SectionReveal delay={200}>
            <div className="space-y-4 max-w-2xl mx-auto">
              <p className="text-xl sm:text-2xl text-[var(--sandstone-light)]/90 font-light leading-relaxed italic">
                "Nothing disappears completely."
              </p>
              <p className="text-xl sm:text-2xl text-[var(--gold-muted)] font-light leading-relaxed italic">
                "Some things are simply buried."
              </p>
            </div>
          </SectionReveal>

          <SectionReveal delay={400}>
            <div className="mt-12 flex justify-center items-center gap-6 text-[var(--gold-muted)]/40 text-xl">
              <span>◈</span>
              <span>𓏏</span>
              <span>𓉐</span>
              <span>𓋹</span>
              <span>◈</span>
            </div>
          </SectionReveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 3: THE ARCHIVE
         ═══════════════════════════════════════════════════════════════ */}
      <section className="relative py-28 lg:py-36 px-6 sm:px-8 border-b border-[var(--gold-muted)]/10">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-16">
            <div>
              <span className="text-xs tracking-[0.25em] text-[var(--gold-muted)]/70 uppercase font-medium">
                Documented Evidence
              </span>
              <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-wide text-[var(--sandstone-light)] mt-2">
                THE ARCHIVE
              </h2>
            </div>
            <div className="max-w-md">
              <p className="text-sm text-[var(--sandstone)]/80 leading-relaxed">
                Fragments of records, observations, and recovered material from preliminary site surveys.
              </p>
              <Link
                to="/archive"
                className="inline-flex items-center gap-2 text-xs font-semibold tracking-wider text-[var(--gold-muted)] hover:text-[#e5c898] mt-2 transition-colors"
              >
                VIEW FULL ARCHIVE INDEX →
              </Link>
            </div>
          </div>

          {/* Archive Record Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {archiveEntries.map((entry, index) => (
              <SectionReveal key={entry.id} delay={index * 120}>
                <div
                  onClick={() =>
                    setExpandedArchive(expandedArchive === entry.id ? null : entry.id)
                  }
                  className={`p-6 sm:p-8 border cursor-pointer transition-all duration-300 ${
                    entry.classification === 'SEALED'
                      ? 'border-[var(--gold-muted)]/40 bg-[var(--dark-earth)]/40 hover:border-[var(--gold-muted)]/70'
                      : 'border-[var(--gold-muted)]/15 bg-[var(--dark-earth)]/25 hover:border-[var(--gold-muted)]/35'
                  }`}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      setExpandedArchive(expandedArchive === entry.id ? null : entry.id);
                    }
                  }}
                  aria-expanded={expandedArchive === entry.id}
                >
                  <div className="flex items-center justify-between gap-4 mb-4">
                    <span className="text-xs font-mono font-medium text-[var(--gold-muted)]">
                      ARCHIVE {entry.id}
                    </span>
                    <span
                      className={`text-xs px-2.5 py-0.5 border ${
                        entry.classification === 'SEALED'
                          ? 'border-[var(--gold-muted)]/50 bg-[var(--gold-muted)]/10 text-[var(--gold-muted)] font-semibold'
                          : entry.classification === 'RESTRICTED'
                          ? 'border-[var(--sandstone)]/30 text-[var(--sandstone)]/80'
                          : 'border-[var(--sandstone)]/20 text-[var(--sandstone)]/60'
                      }`}
                    >
                      {entry.classification}
                    </span>
                  </div>

                  <h3 className="text-lg font-semibold text-[var(--sandstone-light)] mb-2">
                    {entry.title}
                  </h3>

                  <p className="text-sm text-[var(--sandstone)]/75 leading-relaxed mb-4">
                    {entry.excerpt}
                  </p>

                  <div className="flex items-center justify-between text-xs text-[var(--sandstone)]/50 pt-4 border-t border-[var(--gold-muted)]/10">
                    <span>DATE: {entry.date}</span>
                    <span className="text-[var(--gold-muted)]/70">
                      {expandedArchive === entry.id ? '▲ COLLAPSE' : '▼ INSPECT'}
                    </span>
                  </div>

                  {/* Expanded Detail */}
                  {expandedArchive === entry.id && (
                    <div className="mt-4 pt-4 border-t border-[var(--gold-muted)]/20 text-xs text-[var(--sandstone-light)]/80 leading-relaxed bg-[var(--obsidian)]/40 p-3 rounded">
                      <p className="italic">
                        {entry.id === '007'
                          ? 'Anomaly noted: Exterior seal contains no entry marks. Nothing remains exactly as it was found.'
                          : 'Record logged into permanent survey register. Calibration matched to primary stone.'}
                      </p>
                    </div>
                  )}
                </div>
              </SectionReveal>
            ))}
          </div>

          <div className="mt-8 text-center">
            <p className="text-xs text-[var(--sandstone)]/40 tracking-wider">
              [ NOTICE: ARCHIVES 004–006 OMITTED FROM PUBLIC DISCLOSURE ]
            </p>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 4: BEYOND THE SURFACE
         ═══════════════════════════════════════════════════════════════ */}
      <section className="relative py-32 lg:py-40 px-6 sm:px-8 bg-cover bg-center overflow-hidden" style={{ backgroundImage: "url('/images/passage_bg.jpg')" }}>
        <div className="absolute inset-0 bg-[var(--obsidian)]/80 backdrop-blur-[1px]" />

        <div className="relative z-10 max-w-4xl mx-auto text-center">
          <SectionReveal>
            <span className="text-xs tracking-[0.25em] text-[var(--gold-muted)]/80 uppercase font-medium">
              Subterranean Passage
            </span>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-wide text-[var(--sandstone-light)] mt-3 mb-8">
              BEYOND THE SURFACE
            </h2>
          </SectionReveal>

          <SectionReveal delay={200}>
            <div className="max-w-2xl mx-auto space-y-4 mb-12">
              <p className="text-lg sm:text-xl text-[var(--sandstone-light)]/90 leading-relaxed">
                "Every structure has an entrance."
              </p>
              <p className="text-lg sm:text-xl text-[var(--gold-muted)] leading-relaxed">
                "Not every entrance leads where you expect."
              </p>
            </div>
          </SectionReveal>

          <SectionReveal delay={400}>
            <div className="inline-flex items-center gap-6 p-6 rounded-lg bg-[var(--obsidian)]/80 backdrop-blur-md border border-[var(--gold-muted)]/25 text-left max-w-md">
              <div className="text-3xl text-[var(--gold-muted)]">𓉐</div>
              <div>
                <h3 className="text-sm font-semibold text-[var(--sandstone-light)] uppercase tracking-wider">
                  The Second Threshold
                </h3>
                <p className="text-xs text-[var(--sandstone)]/75 mt-1 leading-relaxed">
                  When the initial survey terminates, the true trajectory begins below the foundation line.
                </p>
              </div>
            </div>
          </SectionReveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 5: FINAL CTA
         ═══════════════════════════════════════════════════════════════ */}
      <section className="relative py-32 lg:py-40 px-6 sm:px-8 text-center border-t border-[var(--gold-muted)]/15">
        <div className="max-w-3xl mx-auto">
          <SectionReveal>
            <p className="text-sm sm:text-base text-[var(--sandstone)]/75 tracking-wider uppercase mb-4">
              Perhaps you have seen enough.
            </p>
            <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl text-[var(--sandstone-light)] tracking-wide mb-8">
              ENTER THE MIRAGE
            </h2>
          </SectionReveal>

          <SectionReveal delay={200}>
            <p className="text-base sm:text-lg text-[var(--sandstone)]/80 max-w-xl mx-auto mb-10 leading-relaxed">
              Initiate the passage into the archive environment. Verify the coordinates for yourself.
            </p>

            <Link
              to="/enter"
              className="inline-flex items-center gap-3 px-10 py-5 bg-[var(--gold-muted)] hover:bg-[#c9a648] text-[var(--obsidian)] font-semibold text-sm tracking-widest uppercase transition-all duration-300 shadow-2xl hover:shadow-[0_0_30px_rgba(184,150,62,0.4)]"
            >
              <span>ENTER THE MIRAGE</span>
              <span>→</span>
            </Link>
          </SectionReveal>

          <SectionReveal delay={400}>
            <p className="mt-16 text-xs text-[var(--sandstone)]/40 tracking-wider">
              "Trust what you find. Question where you found it."
            </p>
          </SectionReveal>
        </div>
      </section>
    </main>
  );
}
