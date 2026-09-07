import { useState } from 'react';
import { SectionReveal } from '../components/SectionReveal';

/* ─── Archive data ─── */
type Classification = 'OPEN' | 'RESTRICTED' | 'SEALED' | 'CLASSIFIED';

interface ArchiveEntry {
  id: string;
  title: string;
  date: string;
  classification: Classification;
  excerpt: string;
  expandedContent: string;
  status: string;
}

const archiveEntries: ArchiveEntry[] = [
  {
    id: '001',
    title: 'Foundation',
    date: '1923.03.14',
    classification: 'OPEN',
    excerpt:
      'Initial survey of the western perimeter. The foundation stones were measured and catalogued. All measurements correspond to known architectural records.',
    expandedContent:
      'Survey team consisted of 4 members. Weather conditions: clear, 38°C. Duration: 6 hours. All instruments were calibrated prior to deployment. No anomalies detected in this survey.',
    status: 'Verified',
  },
  {
    id: '002',
    title: 'Observation',
    date: '1923.06.02',
    classification: 'OPEN',
    excerpt:
      'Field notes from the second expedition. Ambient conditions were recorded at regular intervals. Nothing unusual was reported by the primary team.',
    expandedContent:
      'Equipment: standard survey instruments, photographic plates. 47 photographs taken. All exposures developed normally. Temperature variance logged at 2-hour intervals.',
    status: 'Verified',
  },
  {
    id: '003',
    title: 'Reflection',
    date: '1924.11.08',
    classification: 'RESTRICTED',
    excerpt:
      'A secondary team reported a discrepancy in the eastern measurements. The walls appeared to extend beyond the original survey boundaries. This record was later amended.',
    expandedContent:
      'Note: Cross-reference with Archive 007. The amendment was filed by a different team than the original surveyors. The reason for restriction was not documented.',
    status: 'Amended',
  },
  {
    // Gap: 004, 005, 006 are missing
    id: '007',
    title: 'Unclassified',
    date: '1925.██.██',
    classification: 'SEALED',
    excerpt:
      'Everything here has been preserved exactly as it was found. The passage was sealed from the inside. No tool marks were found on the exterior.',
    // Contradicts the excerpt
    expandedContent: 'Nothing remains exactly as it was found.',
    status: 'Pending Review',
  },
  {
    id: '008',
    title: 'Passage',
    date: '1926.01.15',
    classification: 'OPEN',
    excerpt:
      'The secondary entrance was documented but not explored. Access requires specific authorization. The passage dimensions suggest it was not intended for regular use.',
    expandedContent:
      'Passage width: 0.8m. Height: 1.4m. Orientation: descending at approximately 26° from horizontal. Air movement detected from within. No further investigation was authorized.',
    status: 'Documented',
  },
  {
    // Gap: 009, 010 are missing
    id: '011',
    title: 'Incident',
    date: '1927.09.03',
    classification: 'CLASSIFIED',
    excerpt:
      'Survey equipment was recovered from the lower chamber. The equipment was functional. The operator was not found. This record has been flagged for internal review.',
    expandedContent:
      'Equipment serial numbers match those assigned to the secondary survey team. Last calibration date on the instruments: 1927.08.28. Battery levels indicated recent use. No further details available at this clearance level.',
    status: 'Under Review',
  },
];

const classificationFilters: ('ALL' | Classification)[] = [
  'ALL',
  'OPEN',
  'RESTRICTED',
  'SEALED',
  'CLASSIFIED',
];

export function ArchivePage() {
  const [activeFilter, setActiveFilter] = useState<'ALL' | Classification>('ALL');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filteredEntries =
    activeFilter === 'ALL'
      ? archiveEntries
      : archiveEntries.filter((e) => e.classification === activeFilter);

  return (
    <main className="min-h-screen" data-layer="surface">
      {/* Header */}
      <section className="pt-32 pb-16 lg:pt-40 lg:pb-24 px-6 text-center">
        <SectionReveal>
          <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-8 uppercase">
            Records
          </p>
          <h1 className="font-display text-4xl md:text-5xl lg:text-6xl text-[var(--sandstone-light)] tracking-wide mb-6">
            THE ARCHIVE
          </h1>
          <p className="text-base text-[var(--sandstone)]/75 max-w-lg mx-auto leading-relaxed">
            Fragments of records, observations, and recovered material. Some records may be
            incomplete.
          </p>
        </SectionReveal>
      </section>

      {/* Filter bar */}
      <section className="px-6 mb-12">
        <div className="max-w-4xl mx-auto">
          <SectionReveal>
            <div className="flex flex-wrap justify-center gap-3">
              {classificationFilters.map((filter) => (
                <button
                  key={filter}
                  onClick={() => setActiveFilter(filter)}
                  className={`px-4 py-2 text-xs font-medium tracking-wider border transition-all duration-500 cursor-pointer ${
                    activeFilter === filter
                      ? 'border-[var(--gold-muted)]/60 text-[var(--gold-muted)] bg-[var(--gold-muted)]/10'
                      : 'border-[var(--gold-muted)]/20 text-[var(--sandstone)]/70 hover:border-[var(--gold-muted)]/40 hover:text-[var(--sandstone-light)]'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </SectionReveal>
        </div>
      </section>

      {/* Archive entries */}
      <section className="px-6 pb-24">
        <div className="max-w-4xl mx-auto space-y-4">
          {filteredEntries.map((entry, index) => (
            <SectionReveal key={entry.id} delay={index * 100}>
              <div
                className={`border transition-all duration-500 ${
                  entry.classification === 'SEALED'
                    ? 'border-[var(--gold-muted)]/30 bg-[var(--dark-earth)]/50'
                    : entry.classification === 'CLASSIFIED'
                    ? 'border-[var(--gold-muted)]/20 bg-[var(--dark-earth)]/40'
                    : 'border-[var(--gold-muted)]/15 bg-[var(--dark-earth)]/25'
                } hover:border-[var(--gold-muted)]/35`}
              >
                <button
                  onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                  className="w-full text-left p-6 lg:p-8 cursor-pointer"
                  aria-expanded={expandedId === entry.id}
                >
                  {/* Header */}
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className="text-xs tracking-wider text-[var(--gold-muted)]/70 font-medium">
                          ARCHIVE {entry.id}
                        </span>
                        <span
                          className={`text-xs tracking-wide px-2 py-0.5 border ${
                            entry.classification === 'SEALED'
                              ? 'border-[var(--gold-muted)]/40 text-[var(--gold-muted)]/90 bg-[var(--gold-muted)]/5'
                              : entry.classification === 'CLASSIFIED'
                              ? 'border-[var(--gold-muted)]/30 text-[var(--gold-muted)]/80'
                              : entry.classification === 'RESTRICTED'
                              ? 'border-[var(--sandstone)]/30 text-[var(--sandstone)]/80'
                              : 'border-[var(--sandstone)]/20 text-[var(--sandstone)]/60'
                          }`}
                        >
                          {entry.classification}
                        </span>
                      </div>
                      <h2 className="text-xl font-semibold tracking-wide text-[var(--sandstone-light)]">
                        {entry.title}
                      </h2>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs tracking-wider text-[var(--sandstone)]/60">
                        {entry.date}
                      </p>
                      <p className="text-xs tracking-wider text-[var(--sandstone)]/50 mt-1">
                        Status: {entry.status}
                      </p>
                    </div>
                  </div>

                  {/* Excerpt */}
                  <p className="text-sm text-[var(--sandstone)]/75 leading-relaxed">
                    {entry.excerpt}
                  </p>

                  {/* Expand indicator */}
                  <div className="mt-4 flex items-center gap-2">
                    <div className="w-4 h-px bg-[var(--gold-muted)]/30" />
                    <span className="text-xs tracking-wider text-[var(--sandstone)]/50">
                      {expandedId === entry.id ? 'COLLAPSE' : 'EXPAND'}
                    </span>
                  </div>
                </button>

                {/* Expanded content */}
                <div
                  className={`overflow-hidden transition-all duration-500 ${
                    expandedId === entry.id ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <div className="px-6 lg:px-8 pb-6 lg:pb-8 pt-2 border-t border-[var(--gold-muted)]/10">
                    <p className="text-sm text-[var(--sandstone)]/70 leading-relaxed italic">
                      {entry.expandedContent}
                    </p>
                  </div>
                </div>
              </div>
            </SectionReveal>
          ))}

          {/* No results */}
          {filteredEntries.length === 0 && (
            <div className="text-center py-16">
              <p className="text-base text-[var(--sandstone)]/50 tracking-wider">
                No records found for this classification level.
              </p>
            </div>
          )}
        </div>

        {/* Missing records note */}
        <SectionReveal>
          <div className="max-w-4xl mx-auto mt-12 text-center space-y-2">
            <p className="text-xs text-[var(--sandstone)]/20 tracking-wider">
              RECORDS 004–006 AND 009–010 NOT FOUND IN THIS INDEX
            </p>
            <p className="text-xs text-[var(--sandstone)]/20 tracking-wider">
              SOME RECORDS HAVE BEEN REDACTED OR ARE NO LONGER AVAILABLE IN THIS INDEX
            </p>
          </div>
        </SectionReveal>
      </section>
    </main>
  );
}
