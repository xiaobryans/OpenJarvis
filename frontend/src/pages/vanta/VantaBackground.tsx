// VantaBackground — deep-navy field with a perspective grid (mouse parallax),
// a floating particle network (dots linked when close), and a periodic scan line.

import React from 'react';
import { VANTA } from './vanta-kit';

const COUNT = 56;

export function VantaBackground(): React.ReactElement {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const gridRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let w = (canvas.width = canvas.offsetWidth);
    let h = (canvas.height = canvas.offsetHeight);
    const pts = Array.from({ length: COUNT }, () => ({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25 }));

    const onResize = () => { w = canvas.width = canvas.offsetWidth; h = canvas.height = canvas.offsetHeight; };
    window.addEventListener('resize', onResize);

    let raf = 0;
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
      }
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y;
          const d = Math.hypot(dx, dy);
          if (d < 130) {
            ctx.strokeStyle = `rgba(0,200,255,${0.10 * (1 - d / 130)})`;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y); ctx.stroke();
          }
        }
      }
      for (const p of pts) {
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0,212,255,0.5)'; ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    const onMove = (e: MouseEvent) => {
      if (!gridRef.current) return;
      const dx = (e.clientX / window.innerWidth - 0.5) * 22;
      const dy = (e.clientY / window.innerHeight - 0.5) * 22;
      gridRef.current.style.transform = `translate(${-dx}px, ${-dy}px)`;
    };
    window.addEventListener('mousemove', onMove);

    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); window.removeEventListener('mousemove', onMove); };
  }, []);

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0, background: VANTA.bg }}>
      {/* perspective grid (parallax) */}
      <div ref={gridRef} style={{ position: 'absolute', inset: -30, transition: 'transform 0.2s ease-out',
        background: 'repeating-linear-gradient(0deg, transparent, transparent 43px, rgba(0,180,255,0.05) 44px), repeating-linear-gradient(90deg, transparent, transparent 43px, rgba(0,180,255,0.05) 44px)' }} />
      {/* receding floor grid */}
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: '45%',
        background: 'repeating-linear-gradient(0deg, transparent, transparent 20px, rgba(0,180,255,0.06) 21px)',
        transform: 'perspective(420px) rotateX(64deg)', transformOrigin: 'bottom', opacity: 0.5,
        maskImage: 'linear-gradient(to top, black, transparent)', WebkitMaskImage: 'linear-gradient(to top, black, transparent)' }} />
      {/* radial vignette behind orb */}
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(600px 600px at 50% 50%, rgba(0,200,255,0.05), transparent 70%)' }} />
      {/* particle network */}
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      {/* scan line */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: '22vh',
        background: 'linear-gradient(to bottom, transparent, rgba(0,212,255,0.05) 50%, transparent)', animation: 'vScan 10s linear infinite' }} />
    </div>
  );
}
