// VantaOrb — the #cc centre cluster from the reference: state label + readout,
// #osvg orbital rings with glowing travelling dots, #csvg dashed connectors,
// #og glow + #orb sphere + 3 pulse rings, 5 node badges positioned by angle/
// radius around the core, and the pipeline chain.

import React from 'react';
import { VantaTranscript } from './VantaTranscript';

interface NodeDef { id: string; angle: number; r: number; label: string; sub: string; nb?: string; dot?: string }
const NODES: NodeDef[] = [
  { id: 'nd0', angle: 270, r: 205, label: 'PA', sub: 'PERSONAL ASST' },
  { id: 'nd1', angle: 22, r: 202, label: 'COS / GM', sub: 'CHIEF OF STAFF', nb: 'tl' },
  { id: 'nd2', angle: 182, r: 198, label: 'REV', sub: 'REVENUE', nb: 'am', dot: 'am' },
  { id: 'nd3', angle: 218, r: 188, label: 'Wx35', sub: 'WORKFLOWS', nb: 'gr' },
  { id: 'nd4', angle: 147, r: 193, label: 'Mx17', sub: 'MEMORY', nb: 'pu' },
];
const PIPE: [string, string, string][] = [
  ['CLASSIFY', 'INPUT', 'dn'], ['ROUTE', 'DISPATCH', 'dn'], ['MANAGER', 'ACTIVE', 'ac'],
  ['WORKER', 'STANDBY', ''], ['QUALITY', 'GATE', ''], ['COS/GM', 'REVIEW', ''], ['RESPOND', 'OUTPUT', 'dm2'],
];

export function VantaOrb({ stateLabel, stateColor, readout }: { stateLabel: string; stateColor: string; readout: string }): React.ReactElement {
  const cc = React.useRef<HTMLDivElement | null>(null);
  const csvg = React.useRef<SVGSVGElement | null>(null);
  const nodeRefs = React.useRef<Record<string, HTMLDivElement | null>>({});

  React.useEffect(() => {
    const pos = () => {
      const el = cc.current, svg = csvg.current; if (!el || !svg) return;
      const rect = el.getBoundingClientRect();
      const cx = rect.width / 2, cy = rect.height / 2 - 24;
      svg.setAttribute('width', String(rect.width)); svg.setAttribute('height', String(rect.height));
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const NS = 'http://www.w3.org/2000/svg';
      NODES.forEach((n) => {
        const rad = (n.angle * Math.PI) / 180;
        const x = cx + n.r * Math.cos(rad), y = cy + n.r * Math.sin(rad);
        const node = nodeRefs.current[n.id];
        if (node) { node.style.left = `${x}px`; node.style.top = `${y}px`; }
        const ln = document.createElementNS(NS, 'line');
        ln.setAttribute('x1', String(cx)); ln.setAttribute('y1', String(cy));
        ln.setAttribute('x2', String(x)); ln.setAttribute('y2', String(y));
        ln.setAttribute('stroke', 'rgba(0,180,255,.18)'); ln.setAttribute('stroke-width', '1'); ln.setAttribute('stroke-dasharray', '4,7');
        svg.appendChild(ln);
        const mp = document.createElementNS(NS, 'circle');
        mp.setAttribute('cx', String(cx + (x - cx) * 0.62)); mp.setAttribute('cy', String(cy + (y - cy) * 0.62));
        mp.setAttribute('r', '2'); mp.setAttribute('fill', 'rgba(0,212,255,.55)');
        svg.appendChild(mp);
      });
    };
    pos();
    window.addEventListener('resize', pos);
    const ro = new ResizeObserver(pos); if (cc.current) ro.observe(cc.current);
    return () => { window.removeEventListener('resize', pos); ro.disconnect(); };
  }, []);

  return (
    <div id="cc" ref={cc}>
      <div id="stlb" style={{ color: stateColor, textShadow: `0 0 18px ${stateColor}` }}>{stateLabel}</div>
      <div id="rdout">{readout}</div>

      <svg id="osvg" viewBox="0 0 480 480" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="gf"><feGaussianBlur stdDeviation="2.5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <g id="rg1">
          <ellipse cx="240" cy="240" rx="195" ry="62" fill="none" stroke="rgba(0,212,255,.38)" strokeWidth="1.3" />
          <circle cx="435" cy="240" r="5" fill="#00D4FF" filter="url(#gf)" opacity=".95" />
          <circle cx="435" cy="240" r="2.5" fill="white" />
        </g>
        <g id="rg2">
          <ellipse cx="240" cy="240" rx="178" ry="56" fill="none" stroke="rgba(0,212,255,.2)" strokeWidth="1" transform="rotate(55,240,240)" />
          <circle cx="418" cy="240" r="3.5" fill="rgba(0,245,212,.85)" filter="url(#gf)" />
        </g>
        <g id="rg3">
          <ellipse cx="240" cy="240" rx="162" ry="50" fill="none" stroke="rgba(100,200,255,.15)" strokeWidth=".8" transform="rotate(-38,240,240)" />
          <circle cx="402" cy="240" r="3" fill="rgba(189,96,255,.8)" filter="url(#gf)" />
        </g>
      </svg>

      <svg id="csvg" ref={csvg} xmlns="http://www.w3.org/2000/svg" />

      <div id="ow">
        <div id="og" />
        <div id="orb"><div className="pr" /><div className="pr" /><div className="pr" /></div>
      </div>

      {NODES.map((n) => (
        <div className="nd" key={n.id} ref={(el) => { nodeRefs.current[n.id] = el; }}>
          <div className={`ndot ${n.dot ?? ''}`} />
          <div className={`nb ${n.nb ?? ''}`}>{n.label}</div>
          <div className="nl">{n.sub}</div>
        </div>
      ))}

      <VantaTranscript />

      <div id="pl">
        {PIPE.map(([name, sub, cls], i) => (
          <React.Fragment key={name}>
            <div className="ps"><div className={`pb ${cls}`}>{name}</div><div className="psl">{sub}</div></div>
            {i < PIPE.length - 1 && <span className="par">→</span>}
          </React.Fragment>
        ))}
      </div>
      <div id="pllb">{stateLabel}</div>
    </div>
  );
}
