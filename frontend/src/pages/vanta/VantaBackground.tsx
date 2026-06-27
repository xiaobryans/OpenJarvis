// VantaBackground — #crt CRT overlay, #p particle network (58 nodes, link <95px),
// #g perspective grid with mouse parallax, #sc scan line. Ports the reference.

import React from 'react';

export function VantaBackground(): React.ReactElement {
  const cv = React.useRef<HTMLCanvasElement | null>(null);
  const grid = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const canvas = cv.current; if (!canvas) return;
    const ctx = canvas.getContext('2d'); if (!ctx) return;
    let W = (canvas.width = window.innerWidth), H = (canvas.height = window.innerHeight);
    const rsz = () => { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; };
    window.addEventListener('resize', rsz);
    const pts = Array.from({ length: 58 }, () => ({ x: Math.random() * window.innerWidth, y: Math.random() * window.innerHeight, vx: (Math.random() - 0.5) * 0.22, vy: (Math.random() - 0.5) * 0.22, r: Math.random() * 1.1 + 0.4, op: Math.random() * 0.3 + 0.07 }));
    let raf = 0;
    const dp = () => {
      ctx.clearRect(0, 0, W, H);
      pts.forEach((p) => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = W; if (p.x > W) p.x = 0; if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fillStyle = `rgba(0,180,255,${p.op})`; ctx.fill();
      });
      for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y, d = Math.hypot(dx, dy);
        if (d < 95) { ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y); ctx.strokeStyle = `rgba(0,180,255,${0.065 * (1 - d / 95)})`; ctx.lineWidth = 0.5; ctx.stroke(); }
      }
      raf = requestAnimationFrame(dp);
    };
    dp();

    const onMove = (e: MouseEvent) => {
      if (!grid.current) return;
      const mx = (e.clientX / window.innerWidth - 0.5) * 13;
      const my = (e.clientY / window.innerHeight - 0.5) * 5.5;
      grid.current.style.transform = `perspective(600px) rotateX(${36 + my}deg) translateX(${mx}px) scale(1.5)`;
    };
    window.addEventListener('mousemove', onMove);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', rsz); window.removeEventListener('mousemove', onMove); };
  }, []);

  return (
    <>
      <canvas id="p" ref={cv} />
      <div id="g" ref={grid} />
      <div id="sc" />
      <div id="crt" />
    </>
  );
}
