import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

export type SceneFrame = {
  context: CanvasRenderingContext2D;
  width: number;
  height: number;
  delta: number;
  lowPower: boolean;
};

type CanvasOptions = { automatic: boolean; compact: boolean };

function prefersLowPower() {
  if (typeof navigator === 'undefined') return true;
  const device = navigator as Navigator & {
    deviceMemory?: number;
    connection?: { saveData?: boolean };
  };
  return Boolean(device.connection?.saveData)
    || (device.hardwareConcurrency > 0 && device.hardwareConcurrency <= 4)
    || (device.deviceMemory !== undefined && device.deviceMemory <= 4);
}

/** One visibility-aware scheduler per canvas; static scenes only draw on invalidation. */
export function useCanvasScene(draw: (frame: SceneFrame) => void, options: CanvasOptions) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const drawRef = useRef(draw);
  const optionsRef = useRef(options);
  const scheduleRef = useRef<() => void>(() => {});
  const [supported, setSupported] = useState<boolean | null>(null);
  const [lowPower] = useState(prefersLowPower);
  const invalidate = useCallback(() => scheduleRef.current(), []);

  useLayoutEffect(() => {
    drawRef.current = draw;
    optionsRef.current = options;
    invalidate();
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    const viewport = viewportRef.current;
    if (!canvas || !viewport) return;

    let context: CanvasRenderingContext2D | null = null;
    try {
      context = canvas.getContext('2d', { alpha: true });
    } catch {
      // Older browsers and restricted environments may throw rather than return null.
    }
    setSupported(Boolean(context));
    if (!context) return;
    const ctx = context;

    let frameId = 0;
    let width = 0;
    let height = 0;
    let ratio = 1;
    let lastTime = 0;
    let dirty = true;
    let disposed = false;
    let contextLost = false;
    // Wait for IntersectionObserver's first result before doing automatic work.
    let visible = typeof IntersectionObserver === 'undefined';

    const stop = () => {
      cancelAnimationFrame(frameId);
      frameId = 0;
      lastTime = 0;
    };

    const canDraw = () => !disposed && !contextLost && visible && !document.hidden && width > 0 && height > 0;

    const tick = (now: number) => {
      frameId = 0;
      if (!canDraw()) return;
      const { automatic, compact } = optionsRef.current;
      const interval = 1000 / (lowPower || compact ? 30 : 45);
      if (dirty || !lastTime || now - lastTime >= interval) {
        const delta = automatic && lastTime ? Math.min((now - lastTime) / 1000, 0.05) : 0;
        lastTime = automatic ? now : 0;
        dirty = false;
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);
        ctx.save();
        drawRef.current({ context: ctx, width, height, delta, lowPower: lowPower || compact || width < 420 });
        ctx.restore();
      }
      if (automatic && canDraw()) frameId = requestAnimationFrame(tick);
    };

    const schedule = () => {
      dirty = true;
      if (!frameId && canDraw()) frameId = requestAnimationFrame(tick);
    };
    scheduleRef.current = schedule;

    const checkVisibility = () => {
      const bounds = viewport.getBoundingClientRect();
      const next = bounds.bottom > 0 && bounds.top < window.innerHeight
        && bounds.right > 0 && bounds.left < window.innerWidth;
      if (next === visible) return;
      visible = next;
      if (visible) schedule();
      else stop();
    };

    const resize = () => {
      const bounds = viewport.getBoundingClientRect();
      width = bounds.width;
      height = bounds.height;
      // Bound both DPR and total backing pixels on large displays.
      ratio = Math.min(window.devicePixelRatio || 1, lowPower ? 1.25 : 2,
        Math.sqrt(1_800_000 / Math.max(1, width * height)));
      const pixelWidth = Math.max(1, Math.round(width * ratio));
      const pixelHeight = Math.max(1, Math.round(height * ratio));
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
      }
      if (typeof IntersectionObserver === 'undefined') checkVisibility();
      schedule();
    };

    const onVisibility = () => {
      if (document.hidden) stop();
      else schedule();
    };
    const onContextLost = (event: Event) => {
      event.preventDefault();
      contextLost = true;
      stop();
      setSupported(false);
    };
    const onContextRestored = () => {
      contextLost = false;
      setSupported(true);
      resize();
    };

    const intersection = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) schedule();
      else stop();
    });
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(resize);
    intersection?.observe(viewport);
    observer?.observe(viewport);
    if (!intersection) window.addEventListener('scroll', checkVisibility, { capture: true, passive: true });
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('resize', resize);
    canvas.addEventListener('contextlost', onContextLost);
    canvas.addEventListener('contextrestored', onContextRestored);
    resize();

    return () => {
      disposed = true;
      stop();
      scheduleRef.current = () => {};
      intersection?.disconnect();
      observer?.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('resize', resize);
      window.removeEventListener('scroll', checkVisibility, true);
      canvas.removeEventListener('contextlost', onContextLost);
      canvas.removeEventListener('contextrestored', onContextRestored);
    };
  }, [lowPower]);

  return { canvasRef, viewportRef, supported, invalidate };
}
