import { useEffect, useRef } from 'react';

/**
 * Animated SVG pyramid with atmospheric effects.
 * Creates a cinematic desert scene with dust particles, haze, and subtle lighting.
 */
export function PyramidScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = canvas.offsetWidth;
    let height = canvas.offsetHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      width = canvas.offsetWidth;
      height = canvas.offsetHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
    };

    resize();
    window.addEventListener('resize', resize);

    // Dust particles
    interface Particle {
      x: number;
      y: number;
      size: number;
      opacity: number;
      speedX: number;
      speedY: number;
    }

    const particles: Particle[] = [];
    const PARTICLE_COUNT = 60;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        size: Math.random() * 2 + 0.5,
        opacity: Math.random() * 0.3 + 0.05,
        speedX: (Math.random() - 0.5) * 0.3,
        speedY: (Math.random() - 0.3) * 0.15,
      });
    }

    let time = 0;

    const draw = () => {
      time += 0.005;
      ctx.clearRect(0, 0, width, height);

      // Sky gradient (dusk)
      const skyGrad = ctx.createLinearGradient(0, 0, 0, height * 0.65);
      skyGrad.addColorStop(0, '#0d0a07');
      skyGrad.addColorStop(0.3, '#1a1209');
      skyGrad.addColorStop(0.5, '#2d1c0e');
      skyGrad.addColorStop(0.7, '#4a2e15');
      skyGrad.addColorStop(0.85, '#6b3d1a');
      skyGrad.addColorStop(1, '#8a5020');
      ctx.fillStyle = skyGrad;
      ctx.fillRect(0, 0, width, height);

      // Distant dunes/mountains
      const duneY = height * 0.58;
      ctx.beginPath();
      ctx.moveTo(0, duneY + 30);
      for (let x = 0; x <= width; x += 2) {
        const y = duneY + Math.sin(x * 0.003 + 1) * 25 + Math.sin(x * 0.007) * 12;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(width, height);
      ctx.lineTo(0, height);
      ctx.closePath();
      const duneGrad = ctx.createLinearGradient(0, duneY - 20, 0, height);
      duneGrad.addColorStop(0, '#3d2e1f');
      duneGrad.addColorStop(0.4, '#2a1f14');
      duneGrad.addColorStop(1, '#1a1209');
      ctx.fillStyle = duneGrad;
      ctx.fill();

      // Ground/desert floor
      const groundY = height * 0.68;
      ctx.beginPath();
      ctx.moveTo(0, groundY);
      for (let x = 0; x <= width; x += 2) {
        const y = groundY + Math.sin(x * 0.005 + 0.5) * 5 + Math.sin(x * 0.01) * 3;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(width, height);
      ctx.lineTo(0, height);
      ctx.closePath();
      const groundGrad = ctx.createLinearGradient(0, groundY, 0, height);
      groundGrad.addColorStop(0, '#2a1f14');
      groundGrad.addColorStop(1, '#0d0a07');
      ctx.fillStyle = groundGrad;
      ctx.fill();

      // Main pyramid
      const pyrBaseY = height * 0.68;
      const pyrWidth = Math.min(width * 0.45, 500);
      const pyrHeight = pyrWidth * 0.7;
      const pyrCenterX = width * 0.5;
      const pyrTopY = pyrBaseY - pyrHeight;

      // Pyramid shadow (long shadow to the right)
      ctx.beginPath();
      ctx.moveTo(pyrCenterX, pyrTopY);
      ctx.lineTo(pyrCenterX + pyrWidth / 2, pyrBaseY);
      ctx.lineTo(pyrCenterX + pyrWidth * 0.8, pyrBaseY + 10);
      ctx.lineTo(pyrCenterX + pyrWidth / 2 + 20, pyrBaseY);
      ctx.closePath();
      ctx.fillStyle = 'rgba(10, 7, 4, 0.4)';
      ctx.fill();

      // Pyramid left face (darker, shadow side)
      ctx.beginPath();
      ctx.moveTo(pyrCenterX, pyrTopY);
      ctx.lineTo(pyrCenterX - pyrWidth / 2, pyrBaseY);
      ctx.lineTo(pyrCenterX, pyrBaseY);
      ctx.closePath();
      const leftGrad = ctx.createLinearGradient(
        pyrCenterX - pyrWidth / 2, pyrBaseY,
        pyrCenterX, pyrTopY
      );
      leftGrad.addColorStop(0, '#3d2e1f');
      leftGrad.addColorStop(0.5, '#52402e');
      leftGrad.addColorStop(1, '#6b5238');
      ctx.fillStyle = leftGrad;
      ctx.fill();

      // Pyramid right face (lit side)
      ctx.beginPath();
      ctx.moveTo(pyrCenterX, pyrTopY);
      ctx.lineTo(pyrCenterX + pyrWidth / 2, pyrBaseY);
      ctx.lineTo(pyrCenterX, pyrBaseY);
      ctx.closePath();
      const rightGrad = ctx.createLinearGradient(
        pyrCenterX + pyrWidth / 2, pyrBaseY,
        pyrCenterX, pyrTopY
      );
      rightGrad.addColorStop(0, '#6b5238');
      rightGrad.addColorStop(0.4, '#8a6d45');
      rightGrad.addColorStop(0.8, '#a07d4f');
      rightGrad.addColorStop(1, '#b8963e');
      ctx.fillStyle = rightGrad;
      ctx.fill();

      // Stone block lines on right face
      ctx.strokeStyle = 'rgba(180, 150, 110, 0.08)';
      ctx.lineWidth = 0.5;
      const blockRows = 14;
      for (let i = 1; i < blockRows; i++) {
        const t = i / blockRows;
        const rowY = pyrTopY + (pyrBaseY - pyrTopY) * t;
        const rowLeftX = pyrCenterX;
        const rowRightX = pyrCenterX + (pyrWidth / 2) * t;
        ctx.beginPath();
        ctx.moveTo(rowLeftX, rowY);
        ctx.lineTo(rowRightX, rowY);
        ctx.stroke();
      }

      // Stone block lines on left face
      for (let i = 1; i < blockRows; i++) {
        const t = i / blockRows;
        const rowY = pyrTopY + (pyrBaseY - pyrTopY) * t;
        const rowLeftX = pyrCenterX - (pyrWidth / 2) * t;
        const rowRightX = pyrCenterX;
        ctx.beginPath();
        ctx.moveTo(rowLeftX, rowY);
        ctx.lineTo(rowRightX, rowY);
        ctx.stroke();
      }

      // Subtle glow at pyramid top
      const glowIntensity = 0.15 + Math.sin(time * 2) * 0.05;
      const topGlow = ctx.createRadialGradient(
        pyrCenterX, pyrTopY, 0,
        pyrCenterX, pyrTopY, pyrWidth * 0.3
      );
      topGlow.addColorStop(0, `rgba(184, 150, 62, ${glowIntensity})`);
      topGlow.addColorStop(0.5, `rgba(184, 150, 62, ${glowIntensity * 0.3})`);
      topGlow.addColorStop(1, 'rgba(184, 150, 62, 0)');
      ctx.fillStyle = topGlow;
      ctx.fillRect(0, 0, width, height);

      // Sun/moon glow on horizon
      const sunX = width * 0.75;
      const sunY = height * 0.5;
      const sunGlow = ctx.createRadialGradient(sunX, sunY, 0, sunX, sunY, width * 0.4);
      sunGlow.addColorStop(0, 'rgba(200, 150, 60, 0.12)');
      sunGlow.addColorStop(0.3, 'rgba(180, 120, 40, 0.06)');
      sunGlow.addColorStop(1, 'rgba(180, 120, 40, 0)');
      ctx.fillStyle = sunGlow;
      ctx.fillRect(0, 0, width, height);

      // Stars (very subtle, high in the sky)
      for (let i = 0; i < 30; i++) {
        const sx = (Math.sin(i * 127.1 + 311.7) * 0.5 + 0.5) * width;
        const sy = (Math.sin(i * 269.5 + 183.3) * 0.5 + 0.5) * height * 0.35;
        const sop = 0.1 + Math.sin(time * 3 + i) * 0.05;
        const ss = 0.5 + Math.sin(i * 73.1) * 0.3;
        ctx.beginPath();
        ctx.arc(sx, sy, ss, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(230, 220, 200, ${sop})`;
        ctx.fill();
      }

      // Atmospheric haze layer
      const hazeGrad = ctx.createLinearGradient(0, height * 0.5, 0, height * 0.75);
      const hazeOp = 0.08 + Math.sin(time) * 0.02;
      hazeGrad.addColorStop(0, `rgba(180, 150, 110, 0)`);
      hazeGrad.addColorStop(0.5, `rgba(180, 150, 110, ${hazeOp})`);
      hazeGrad.addColorStop(1, `rgba(180, 150, 110, 0)`);
      ctx.fillStyle = hazeGrad;
      ctx.fillRect(0, 0, width, height);

      // Dust particles
      particles.forEach((p) => {
        p.x += p.speedX + Math.sin(time + p.y * 0.01) * 0.1;
        p.y += p.speedY;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        const flickerOp = p.opacity + Math.sin(time * 2 + p.x) * 0.05;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(212, 184, 150, ${Math.max(0, flickerOp)})`;
        ctx.fill();
      });

      // Vignette
      const vignette = ctx.createRadialGradient(
        width / 2, height / 2, height * 0.3,
        width / 2, height / 2, height
      );
      vignette.addColorStop(0, 'rgba(13, 10, 7, 0)');
      vignette.addColorStop(1, 'rgba(13, 10, 7, 0.6)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, width, height);

      animationRef.current = requestAnimationFrame(draw);
    };

    animationRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animationRef.current);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      aria-hidden="true"
    />
  );
}
