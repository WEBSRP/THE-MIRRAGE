import { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';

interface Ripple {
  x: number;
  y: number;
  radius: number;
  maxRadius: number;
  opacity: number;
  speed: number;
}

export function InteractiveOasisHero() {
  const [isEvaporated, setIsEvaporated] = useState(false);
  const [isEvaporating, setIsEvaporating] = useState(false);
  const [showNotification, setShowNotification] = useState(false);
  const [hoverWater, setHoverWater] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const ripplesRef = useRef<Ripple[]>([]);
  const animationFrameRef = useRef<number>(0);

  // Trigger ripple at coordinate
  const addRipple = useCallback((x: number, y: number, isStrong = false) => {
    ripplesRef.current.push({
      x,
      y,
      radius: 0,
      maxRadius: isStrong ? 180 : 70,
      opacity: isStrong ? 0.9 : 0.45,
      speed: isStrong ? 3.5 : 1.8,
    });
  }, []);

  // Canvas animation loop for water ripples and heat shimmer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };

    window.addEventListener('resize', handleResize);

    let time = 0;

    const render = () => {
      time += 0.03;
      ctx.clearRect(0, 0, width, height);

      // Render ripples if pond is visible
      if (!isEvaporated || isEvaporating) {
        for (let i = ripplesRef.current.length - 1; i >= 0; i--) {
          const r = ripplesRef.current[i];
          r.radius += r.speed;
          r.opacity -= 0.012;

          if (r.opacity <= 0 || r.radius >= r.maxRadius) {
            ripplesRef.current.splice(i, 1);
            continue;
          }

          ctx.save();
          ctx.beginPath();
          // Elliptical ripple matching perspective of water surface
          ctx.ellipse(r.x, r.y, r.radius, r.radius * 0.45, 0, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(230, 245, 255, ${Math.max(0, r.opacity)})`;
          ctx.lineWidth = 1.5;
          ctx.shadowColor = 'rgba(180, 220, 255, 0.4)';
          ctx.shadowBlur = 4;
          ctx.stroke();

          // Second concentric ring
          if (r.radius > 15) {
            ctx.beginPath();
            ctx.ellipse(r.x, r.y, r.radius * 0.65, r.radius * 0.65 * 0.45, 0, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(190, 230, 255, ${Math.max(0, r.opacity * 0.6)})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
          ctx.restore();
        }

        // Ambient gentle water shimmer near bottom center (water area)
        if (hoverWater && Math.random() < 0.15) {
          const randomX = width * (0.35 + Math.random() * 0.3);
          const randomY = height * (0.65 + Math.random() * 0.25);
          addRipple(randomX, randomY, false);
        }
      }

      // Heat shimmer particles when evaporated
      if (isEvaporated) {
        ctx.save();
        for (let i = 0; i < 20; i++) {
          const px = (Math.sin(time * 0.5 + i * 2) * 0.4 + 0.5) * width;
          const py = height * 0.6 + ((i * 17 + time * 30) % (height * 0.35));
          const pAlpha = Math.sin((py / height) * Math.PI) * 0.15;
          ctx.fillStyle = `rgba(212, 184, 150, ${pAlpha})`;
          ctx.beginPath();
          ctx.arc(px, py, 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }

      animationFrameRef.current = requestAnimationFrame(render);
    };

    animationFrameRef.current = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameRef.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [isEvaporated, isEvaporating, hoverWater, addRipple]);

  // Handle clicking / touching the illusion pond
  const handleOasisInteraction = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (!isEvaporated && !isEvaporating) {
      // Create dramatic ripple sequence
      addRipple(x, y, true);
      setTimeout(() => addRipple(x + 20, y - 10, true), 120);
      setTimeout(() => addRipple(x - 20, y + 10, true), 240);

      setIsEvaporating(true);

      // Trigger evaporation
      setTimeout(() => {
        setIsEvaporated(true);
        setIsEvaporating(false);
        setShowNotification(true);

        setTimeout(() => {
          setShowNotification(false);
        }, 6000);
      }, 900);
    } else if (isEvaporated && !isEvaporating) {
      // Restore illusion
      setIsEvaporating(true);
      setTimeout(() => {
        setIsEvaporated(false);
        setIsEvaporating(false);
        addRipple(x, y, true);
      }, 500);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if cursor is in the lower half (water pond zone)
    if (y > rect.height * 0.55 && Math.random() < 0.25) {
      addRipple(x, y, false);
    }
  };

  return (
    <section className="relative w-full min-h-screen flex flex-col justify-between overflow-hidden select-none bg-[var(--obsidian)]">
      {/* ═══════════════════════════════════════════════════════════════
          ENVIRONMENT LAYERS (Photorealistic Oasis / Dry Ground)
         ═══════════════════════════════════════════════════════════════ */}
      <div
        className="absolute inset-0 w-full h-full cursor-pointer overflow-hidden"
        onClick={handleOasisInteraction}
        onMouseMove={handleMouseMove}
        onMouseEnter={() => setHoverWater(true)}
        onMouseLeave={() => setHoverWater(false)}
        role="region"
        aria-label="Interactive Desert Oasis Illusion"
      >
        {/* Layer 1: Dry Parched Desert Floor (Revealed when pond evaporates) */}
        <div
          className="absolute inset-0 bg-cover bg-center transition-transform duration-1000 scale-100"
          style={{ backgroundImage: "url('/images/dry_hero.jpg')" }}
        />

        {/* Layer 2: Lush Oasis with Water Reflection (Fades/Evaporates on click) */}
        <div
          className={`absolute inset-0 bg-cover bg-center transition-all duration-1000 ease-out ${
            isEvaporated
              ? 'opacity-0 scale-102 filter blur-sm pointer-events-none'
              : isEvaporating
              ? 'opacity-40 filter blur-[2px] brightness-110'
              : 'opacity-100 scale-100'
          }`}
          style={{
            backgroundImage: "url('/images/oasis_hero.jpg')",
          }}
        />

        {/* Layer 3: Interactive Water Ripple & Heat Shimmer Canvas */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none z-10"
        />

        {/* Layer 4: Cinematic Atmosphere & Vignette Overlays */}
        <div className="absolute inset-0 bg-gradient-to-t from-[var(--obsidian)]/90 via-transparent to-[var(--obsidian)]/40 pointer-events-none z-10" />
        <div className="absolute inset-0 bg-gradient-to-r from-[var(--obsidian)]/80 via-transparent to-[var(--obsidian)]/60 pointer-events-none z-10" />

        {/* ═══════════════════════════════════════════════════════════════
            TOUCH THE ILLUSION INDICATOR (Foreground Callout)
           ═══════════════════════════════════════════════════════════════ */}
        <div
          className={`absolute bottom-36 sm:bottom-40 left-1/2 -translate-x-1/2 z-20 transition-all duration-700 pointer-events-none ${
            isEvaporated
              ? 'opacity-90 translate-y-0'
              : 'opacity-85 hover:opacity-100 animate-pulse'
          }`}
        >
          <div className="flex items-center gap-3 px-5 py-2.5 rounded-full bg-[var(--obsidian)]/75 backdrop-blur-md border border-[var(--gold-muted)]/30 shadow-2xl">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--gold-muted)] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[var(--gold-muted)]"></span>
            </span>
            <span className="text-xs tracking-widest uppercase font-medium text-[var(--sandstone-light)]">
              {isEvaporated
                ? 'DESERT FLOOR REVEALED • CLICK TO RESTORE ILLUSION'
                : 'TOUCH THE REFLECTION • INTERACTIVE ILLUSION'}
            </span>
          </div>
        </div>

        {/* Dynamic Deception Message Notification */}
        <div
          className={`absolute top-28 sm:top-32 left-1/2 -translate-x-1/2 z-30 transition-all duration-700 pointer-events-none ${
            showNotification
              ? 'opacity-100 translate-y-0'
              : 'opacity-0 -translate-y-4'
          }`}
        >
          <div className="px-6 py-3 rounded-lg bg-[var(--obsidian)]/90 backdrop-blur-lg border border-[var(--gold-muted)]/40 shadow-2xl text-center max-w-md">
            <p className="text-sm font-medium text-[var(--gold-muted)] tracking-wider">
              "Not everything that reflects is there."
            </p>
            <p className="text-xs text-[var(--sandstone)]/70 mt-1">
              The oasis was a mirage. The desert floor remains unchanged.
            </p>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          HERO CONTENT OVERLAY (Non-blocking UI Layer)
         ═══════════════════════════════════════════════════════════════ */}
      <div className="relative z-20 max-w-7xl w-full mx-auto px-6 sm:px-8 pt-32 sm:pt-40 lg:pt-48 pb-12 pointer-events-none">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
          {/* Left Column: Eyebrow, Main Brand & Primary CTA */}
          <div className="lg:col-span-8 pointer-events-auto">
            {/* Eyebrow */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[var(--obsidian)]/60 backdrop-blur-md border border-[var(--gold-muted)]/20 mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--gold-muted)]" />
              <p className="text-xs tracking-[0.25em] text-[var(--gold-muted)] font-medium uppercase">
                Illusions in Plain Sight
              </p>
            </div>

            {/* Brand Title */}
            <h1 className="font-display text-5xl sm:text-7xl lg:text-8xl tracking-widest text-[var(--sandstone-light)] drop-shadow-2xl mb-6">
              MIRRAGE
            </h1>

            {/* Subtitle */}
            <p className="text-lg sm:text-xl text-[var(--parchment)]/90 max-w-xl font-normal leading-relaxed mb-8 drop-shadow-md">
              "What you see is not what was built."
            </p>

            {/* Primary Action Button */}
            <div className="flex flex-wrap items-center gap-4">
              <Link
                to="/enter"
                className="group relative inline-flex items-center gap-3 px-8 py-4 bg-[var(--gold-muted)] hover:bg-[#c9a648] text-[var(--obsidian)] font-medium text-sm tracking-wider uppercase transition-all duration-300 shadow-xl hover:shadow-[0_0_25px_rgba(184,150,62,0.4)]"
              >
                <span>ENTER THE MIRAGE</span>
                <span className="transition-transform duration-300 group-hover:translate-x-1">
                  →
                </span>
              </Link>

              <Link
                to="/about"
                className="inline-flex items-center gap-2 px-6 py-4 bg-[var(--obsidian)]/70 hover:bg-[var(--obsidian)]/90 text-[var(--sandstone-light)] hover:text-white font-medium text-sm tracking-wider uppercase border border-[var(--gold-muted)]/30 backdrop-blur-md transition-all duration-300"
              >
                THE ARCHITECTURE
              </Link>
            </div>
          </div>

          {/* Right Column: Subtle Thematic Quote Card */}
          <div className="lg:col-span-4 lg:text-right pointer-events-auto">
            <div className="inline-block lg:max-w-xs p-6 bg-[var(--obsidian)]/60 backdrop-blur-md border border-[var(--gold-muted)]/20 text-left">
              <p className="text-xs tracking-widest uppercase text-[var(--gold-muted)]/70 font-medium mb-2">
                Observation 01
              </p>
              <blockquote className="text-sm sm:text-base text-[var(--sandstone-light)]/90 italic leading-relaxed">
                "A reflection can be convincing without being real."
              </blockquote>
              <div className="mt-4 flex items-center justify-between border-t border-[var(--gold-muted)]/15 pt-3">
                <span className="text-xs text-[var(--sandstone)]/50 tracking-wider">
                  SURVEY LOG 1923
                </span>
                <span className="text-xs text-[var(--gold-muted)]/60 font-mono">
                  REF-003
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          BOTTOM TRANSLUCENT INFORMATION BAR (Inspired by reference)
         ═══════════════════════════════════════════════════════════════ */}
      <div className="relative z-20 w-full border-t border-[var(--gold-muted)]/20 bg-[var(--obsidian)]/85 backdrop-blur-xl pointer-events-auto">
        <div className="max-w-7xl mx-auto px-6 sm:px-8 py-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 divide-y md:divide-y-0 md:divide-x divide-[var(--gold-muted)]/15">
            {/* Column 1: Observe */}
            <div className="flex items-start gap-4 pt-4 md:pt-0 md:pr-6">
              <div className="shrink-0 w-10 h-10 rounded border border-[var(--gold-muted)]/30 bg-[var(--dark-earth)]/40 flex items-center justify-center text-[var(--gold-muted)] text-base">
                ◈
              </div>
              <div>
                <h3 className="text-xs tracking-widest uppercase font-semibold text-[var(--sandstone-light)] mb-1">
                  OBSERVE
                </h3>
                <p className="text-xs text-[var(--sandstone)]/80 leading-relaxed">
                  "Look beyond the obvious."
                </p>
              </div>
            </div>

            {/* Column 2: Question */}
            <div className="flex items-start gap-4 pt-4 md:pt-0 md:px-6">
              <div className="shrink-0 w-10 h-10 rounded border border-[var(--gold-muted)]/30 bg-[var(--dark-earth)]/40 flex items-center justify-center text-[var(--gold-muted)] text-base">
                ▲
              </div>
              <div>
                <h3 className="text-xs tracking-widest uppercase font-semibold text-[var(--sandstone-light)] mb-1">
                  QUESTION
                </h3>
                <p className="text-xs text-[var(--sandstone)]/80 leading-relaxed">
                  "The safest path is rarely the true one."
                </p>
              </div>
            </div>

            {/* Column 3: Discover */}
            <div className="flex items-start gap-4 pt-4 md:pt-0 md:pl-6">
              <div className="shrink-0 w-10 h-10 rounded border border-[var(--gold-muted)]/30 bg-[var(--dark-earth)]/40 flex items-center justify-center text-[var(--gold-muted)] text-base">
                𓁹
              </div>
              <div>
                <h3 className="text-xs tracking-widest uppercase font-semibold text-[var(--sandstone-light)] mb-1">
                  DISCOVER
                </h3>
                <p className="text-xs text-[var(--sandstone)]/80 leading-relaxed">
                  "Every monument hides something beneath it."
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
