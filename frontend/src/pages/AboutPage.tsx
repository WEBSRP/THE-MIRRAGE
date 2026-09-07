import { SectionReveal } from '../components/SectionReveal';

export function AboutPage() {
  return (
    <main className="min-h-screen">
      {/* HERO */}
      <section className="pt-32 pb-24 lg:pt-40 lg:pb-36 px-6 flex flex-col items-center justify-center min-h-[50vh] text-center">
        <SectionReveal>
          <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-8 uppercase">
            About
          </p>
          <h1 className="font-display text-4xl md:text-5xl lg:text-6xl text-[var(--sandstone-light)] tracking-wide mb-6">
            ABOUT THE PROJECT
          </h1>
          <p className="text-base md:text-lg text-[var(--sandstone)]/75 leading-relaxed tracking-[0.05em] max-w-2xl mx-auto">
            Understanding what lies beneath perception.
          </p>
        </SectionReveal>
      </section>

      {/* THE ORIGIN */}
      <section className="py-24 lg:py-36 px-6 border-t border-[var(--gold-muted)]/5">
        <div className="max-w-3xl mx-auto">
          <SectionReveal>
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-4 uppercase">
              01 / Foundation
            </p>
            <h2 className="font-display text-3xl md:text-4xl text-[var(--sandstone-light)] tracking-wide mb-12">
              THE ORIGIN
            </h2>
          </SectionReveal>

          <SectionReveal delay={200}>
            <div className="space-y-6 text-base text-[var(--sandstone)]/80 leading-relaxed">
              <p>
                Initiated as an independent architectural and archaeological survey, the MIRRAGE
                project investigates the structural anomalies and perceptual distortions frequently
                encountered at ancient monumental sites. What began as a routine documentation
                effort quickly evolved into a deeper inquiry into how these spaces were engineered
                to manipulate spatial awareness and time.
              </p>
              <p>
                Our primary methodology revolves around passive observation and rigorous, unaltered
                record-keeping. We do not excavate; we observe. By analyzing the intersection of
                light, geometry, and material composition under varying conditions, we document
                phenomena that traditional surveys often dismiss as artifacts of erosion or optical
                illusion.
              </p>
            </div>
          </SectionReveal>

          <SectionReveal delay={400}>
            <blockquote className="my-12 pl-6 border-l border-[var(--gold-muted)]/30">
              <p className="text-lg text-[var(--sandstone-light)]/80 italic tracking-wide">
                "The first thing you find is rarely the first thing that was there."
              </p>
            </blockquote>
          </SectionReveal>
        </div>
      </section>

      {/* THE METHODOLOGY */}
      <section className="py-24 lg:py-36 px-6 border-t border-[var(--gold-muted)]/5">
        <div className="max-w-4xl mx-auto">
          <SectionReveal>
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-4 uppercase">
              02 / Approach
            </p>
            <h2 className="font-display text-3xl md:text-4xl text-[var(--sandstone-light)] tracking-wide mb-16">
              THE METHODOLOGY
            </h2>
          </SectionReveal>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
            {[
              {
                icon: '𓁹',
                title: 'Observation',
                text: 'Careful and sustained documentation of physical sites over extended periods. We prioritize silent observation over intrusive interaction, allowing the structures to reveal their inherent properties.',
              },
              {
                icon: '𓆣',
                title: 'Analysis',
                text: 'Cross-referencing topographical anomalies, lighting patterns, and structural deviations. Data is synthesized to identify recurring architectural motifs that defy conventional explanation.',
              },
              {
                icon: '𓉐',
                title: 'Preservation',
                text: 'Maintaining records exactly as found. Our archives are immutable, ensuring that subsequent interpretations do not alter the foundational observations recorded at the moment of discovery.',
              },
            ].map((card, i) => (
              <SectionReveal key={card.title} delay={i * 150}>
                <div className="p-8 border border-[var(--gold-muted)]/10 bg-[var(--dark-earth)]/20 hover:bg-[var(--dark-earth)]/40 transition-colors duration-500 text-center h-full">
                  <span className="text-3xl text-[var(--gold-muted)]/60 block mb-6" aria-hidden="true">
                    {card.icon}
                  </span>
                  <h3 className="text-lg font-semibold text-[var(--sandstone-light)] tracking-wide mb-4">
                    {card.title.toUpperCase()}
                  </h3>
                  <p className="text-sm text-[var(--sandstone)]/70 leading-relaxed">
                    {card.text}
                  </p>
                </div>
              </SectionReveal>
            ))}
          </div>
        </div>
      </section>

      {/* THE TEAM */}
      <section className="py-24 lg:py-36 px-6 border-t border-[var(--gold-muted)]/5">
        <div className="max-w-3xl mx-auto">
          <SectionReveal>
            <p className="text-xs tracking-widest text-[var(--gold-muted)]/60 mb-4 uppercase">
              03 / Personnel
            </p>
            <h2 className="font-display text-3xl md:text-4xl text-[var(--sandstone-light)] tracking-wide mb-12">
              THE TEAM
            </h2>
          </SectionReveal>

          <SectionReveal delay={200}>
            <div className="space-y-6 text-base text-[var(--sandstone)]/80 leading-relaxed">
              <p>
                The project is maintained by a small group of dedicated observers. We operate
                without institutional oversight to ensure our findings remain uncompromised by
                standard academic biases.
              </p>
              {/* Subtle inconsistency: active since 2019 but references 1923 records */}
              <p>
                Our current configuration has been active since 2019, though our protocols strictly
                adhere to the guidelines established in the original field logs documented during
                the preliminary site assessment in 1923. Continuity of observation is paramount.
              </p>
            </div>
          </SectionReveal>
        </div>
      </section>

      {/* FINAL QUOTE */}
      <section className="py-24 lg:py-48 px-6 text-center">
        <SectionReveal>
          <h2 className="font-display text-2xl md:text-4xl text-[var(--sandstone-light)] tracking-wide">
            LOOK BEYOND THE OBVIOUS.
          </h2>
        </SectionReveal>
      </section>
    </main>
  );
}
