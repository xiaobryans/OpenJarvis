// vanta-hud-styles — faithful port of the jarvis_hud reference CSS, scoped to
// #vanta-root so the generic class names (.hud, .hr, .k, .v …) don't leak into
// the rest of the app. Keyframes are prefixed `vh` to avoid global collisions.

import React from 'react';

export function VantaHudStyles(): React.ReactElement {
  return (
    <style>{`
#vanta-root{position:fixed;inset:0;z-index:0;background:var(--vbg,#020810);color:#8EC8E8;font-family:'JetBrains Mono',monospace;overflow:hidden;
  --c:#00D4FF;--cd:rgba(0,212,255,.3);--cg:rgba(0,212,255,.6);
  --am:#FF9500;--gr:#00FF88;--rd:#FF3355;--pu:#BD60FF;--tl:#00F5D4;
  --bg:#020810;--border:rgba(0,200,255,.28);--txt:#8EC8E8;--dim:rgba(142,200,232,.38);
  --mono:'JetBrains Mono',monospace;--disp:'Orbitron',sans-serif;}
#vanta-root *,#vanta-root *::before,#vanta-root *::after{margin:0;padding:0;box-sizing:border-box}
#vanta-root #crt{content:'';position:absolute;inset:0;background:repeating-linear-gradient(to bottom,transparent 0,transparent 3px,rgba(0,0,0,.032) 3px,rgba(0,0,0,.032) 4px);pointer-events:none;z-index:9999}
#vanta-root #p{position:absolute;inset:0;z-index:1;pointer-events:none}
#vanta-root #g{position:absolute;width:200%;height:200%;left:-50%;top:-50%;background-image:linear-gradient(rgba(0,180,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(0,180,255,.05) 1px,transparent 1px);background-size:58px 58px;transform:perspective(600px) rotateX(36deg) scale(1.5);transform-origin:50% 82%;z-index:2;pointer-events:none}
#vanta-root #sc{position:absolute;left:0;right:0;top:-2px;height:2px;background:linear-gradient(90deg,transparent 0%,var(--cg) 40%,var(--c) 50%,var(--cg) 60%,transparent 100%);box-shadow:0 0 14px rgba(0,212,255,.5),0 0 28px rgba(0,200,255,.2);z-index:4;animation:vhscan 10s ease-in-out infinite;pointer-events:none}
@keyframes vhscan{0%,4%{top:-2px;opacity:0}8%{opacity:1}92%{opacity:.8}96%,100%{top:100%;opacity:0}}
#vanta-root #tb{position:absolute;top:0;left:0;right:0;height:48px;background:rgba(2,8,22,.98);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 14px;gap:10px;z-index:300}
#vanta-root .tbl{font-family:var(--disp);font-size:13px;font-weight:700;letter-spacing:5px;color:var(--c);display:flex;align-items:center;gap:8px}
#vanta-root .tbi{font-size:20px;animation:vhlp 2.5s ease-in-out infinite;text-shadow:0 0 12px var(--c)}
@keyframes vhlp{0%,100%{opacity:1;text-shadow:0 0 12px var(--c)}50%{opacity:.55;text-shadow:0 0 22px var(--c)}}
#vanta-root .tbv{font-size:9px;color:var(--dim);letter-spacing:1.5px;border-left:1px solid var(--border);padding-left:10px}
#vanta-root .tbc{position:absolute;left:50%;transform:translateX(-50%);font-family:var(--disp);font-size:9px;letter-spacing:8px;color:var(--dim)}
#vanta-root .tbs{flex:1}
#vanta-root #clk{font-family:var(--disp);font-size:11px;letter-spacing:3px;color:var(--c)}
#vanta-root .tbi2{font-size:9px;color:var(--dim);letter-spacing:1px;border-left:1px solid var(--border);padding-left:10px}
#vanta-root #app{position:absolute;top:48px;bottom:48px;left:0;right:0;display:grid;grid-template-columns:238px 1fr 238px;z-index:10}
#vanta-root .col{display:flex;flex-direction:column;gap:6px;padding:10px 8px;pointer-events:all;min-height:0}
#vanta-root #cc{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden;pointer-events:all}
#vanta-root .hud{background:linear-gradient(135deg,rgba(0,200,255,.07) 0%,rgba(4,16,40,.16) 40%,rgba(0,80,180,.06) 100%);border:1px solid rgba(0,200,255,.22);padding:10px;position:relative;overflow:hidden;backdrop-filter:blur(22px) saturate(180%);-webkit-backdrop-filter:blur(22px) saturate(180%);box-shadow:inset 0 1px 0 rgba(0,212,255,.12),inset 0 -1px 0 rgba(0,80,200,.08),0 4px 24px rgba(0,0,0,.35);display:flex;flex-direction:column;min-height:0}
#vanta-root .hud::before{content:'';position:absolute;top:0;left:0;width:14px;height:14px;border-top:2px solid var(--c);border-left:2px solid var(--c);opacity:.75}
#vanta-root .hud::after{content:'';position:absolute;bottom:0;right:0;width:14px;height:14px;border-bottom:2px solid var(--c);border-right:2px solid var(--c);opacity:.75}
#vanta-root .htop{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(0,180,255,.1)}
#vanta-root .ht{font-family:var(--disp);font-size:7.5px;letter-spacing:3px;color:var(--c);font-weight:600}
#vanta-root .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
#vanta-root .dg{background:var(--gr);box-shadow:0 0 6px var(--gr);animation:vhdp 2s ease-in-out infinite}
#vanta-root .da{background:var(--am);box-shadow:0 0 6px var(--am);animation:vhdp 1.4s ease-in-out infinite}
#vanta-root .dr{background:var(--rd);box-shadow:0 0 6px var(--rd);animation:vhdp .8s ease-in-out infinite}
@keyframes vhdp{0%,100%{opacity:1}50%{opacity:.25}}
#vanta-root .hr{display:flex;justify-content:space-between;align-items:center;padding:2.5px 0;border-bottom:1px solid rgba(0,180,255,.05);font-size:10px;gap:4px}
#vanta-root .hr:last-child{border-bottom:none}
#vanta-root .k{color:var(--dim);letter-spacing:.5px;white-space:nowrap}
#vanta-root .v{color:var(--txt);text-align:right;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#vanta-root .vg{color:var(--gr)}#vanta-root .va{color:var(--am)}#vanta-root .vr{color:var(--rd)}#vanta-root .vc{color:var(--c)}
#vanta-root .hdv{height:1px;background:rgba(0,180,255,.1);margin:5px -10px}
#vanta-root .bv{font-family:var(--disp);font-size:26px;font-weight:700;color:var(--c);line-height:1;margin:4px 0 0;text-shadow:0 0 20px rgba(0,212,255,.5)}
#vanta-root .bl{font-family:var(--disp);font-size:7px;letter-spacing:3px;color:var(--dim);margin-bottom:6px}
#vanta-root .mw{margin:4px 0}
#vanta-root .ml{display:flex;justify-content:space-between;font-size:10px;color:var(--dim);margin-bottom:2px}
#vanta-root .mb{height:2px;background:rgba(0,180,255,.1);overflow:hidden}
#vanta-root .mf{height:100%;background:linear-gradient(90deg,var(--c),var(--cg));box-shadow:0 0 4px var(--c);transition:width 1.5s ease}
#vanta-root .mfa{background:linear-gradient(90deg,var(--am),rgba(255,149,0,.6))}
#vanta-root .sn{font-size:10px;color:var(--dim);line-height:1.6;letter-spacing:.5px}
#vanta-root .al{padding:3px 6px;border-left:2px solid var(--am);background:rgba(255,149,0,.05);font-size:10px;color:rgba(255,149,0,.8);margin:2px 0;letter-spacing:.5px}
#vanta-root #stlb{position:absolute;top:16px;font-family:var(--disp);font-size:9px;letter-spacing:10px;color:var(--gr);text-shadow:0 0 15px rgba(0,255,136,.5);z-index:30;transition:all .8s ease}
#vanta-root #rdout{position:absolute;top:40px;font-family:var(--disp);font-size:7px;letter-spacing:2px;color:var(--dim);z-index:30;transition:all .5s ease}
#vanta-root #osvg{position:absolute;width:480px;height:480px;left:50%;top:50%;transform:translate(-50%,-50%) translateY(-24px);z-index:8;pointer-events:none}
#vanta-root #rg1{animation:vhcw 12s linear infinite;transform-origin:240px 240px}
#vanta-root #rg2{animation:vhccw 20s linear infinite;transform-origin:240px 240px;animation-delay:-7s}
#vanta-root #rg3{animation:vhcw 34s linear infinite;transform-origin:240px 240px;animation-delay:-14s}
@keyframes vhcw{to{transform:rotate(360deg)}}
@keyframes vhccw{to{transform:rotate(-360deg)}}
#vanta-root #csvg{position:absolute;top:0;left:0;z-index:7;pointer-events:none}
#vanta-root #ow{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) translateY(-24px);width:220px;height:220px;z-index:10}
#vanta-root #og{position:absolute;width:390px;height:390px;left:50%;top:50%;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,rgba(0,160,255,.12) 0%,rgba(0,80,200,.05) 45%,transparent 70%);animation:vhgb 4s ease-in-out infinite;z-index:0;pointer-events:none}
@keyframes vhgb{0%,100%{transform:translate(-50%,-50%) scale(1);opacity:.8}50%{transform:translate(-50%,-50%) scale(1.18);opacity:1}}
#vanta-root #orb{position:absolute;inset:0;border-radius:50%;background:radial-gradient(circle at 34% 28%,rgba(255,255,255,.95) 0%,rgba(160,235,255,.9) 6%,rgba(0,190,255,.88) 22%,rgba(0,120,220,.92) 48%,rgba(0,50,140,.96) 72%,rgba(0,12,45,1) 100%);box-shadow:0 0 35px rgba(0,190,255,.8),0 0 70px rgba(0,160,255,.55),0 0 140px rgba(0,120,220,.3),0 0 220px rgba(0,80,180,.15),inset 0 0 25px rgba(0,80,180,.4),inset -10px -10px 25px rgba(0,0,40,.65);animation:vhob 3.5s ease-in-out infinite;z-index:5}
@keyframes vhob{0%,100%{box-shadow:0 0 35px rgba(0,190,255,.8),0 0 70px rgba(0,160,255,.55),0 0 140px rgba(0,120,220,.3),0 0 220px rgba(0,80,180,.15),inset 0 0 25px rgba(0,80,180,.4),inset -10px -10px 25px rgba(0,0,40,.65)}50%{box-shadow:0 0 55px rgba(0,210,255,.95),0 0 110px rgba(0,190,255,.7),0 0 210px rgba(0,155,255,.42),0 0 330px rgba(0,100,220,.2),inset 0 0 38px rgba(0,105,210,.58),inset -10px -10px 25px rgba(0,0,40,.65)}}
#vanta-root .pr{position:absolute;inset:-15px;border-radius:50%;border:1px solid rgba(0,212,255,.45);animation:vhpe 4s ease-out infinite;z-index:3;pointer-events:none}
#vanta-root .pr:nth-child(2){animation-delay:1.33s}
#vanta-root .pr:nth-child(3){animation-delay:2.66s}
@keyframes vhpe{0%{transform:scale(.95);opacity:.7}100%{transform:scale(2.7);opacity:0}}
#vanta-root .nd{position:absolute;display:flex;flex-direction:column;align-items:center;gap:3px;z-index:20;cursor:pointer;transform:translate(-50%,-50%);transition:all .3s}
#vanta-root .nd:hover .nb{box-shadow:0 0 22px currentColor}
#vanta-root .nb{padding:4px 9px;border:1px solid var(--c);background:rgba(0,50,120,.22);color:var(--c);font-family:var(--disp);font-size:9px;font-weight:700;letter-spacing:2px;box-shadow:0 0 8px rgba(0,212,255,.25);backdrop-filter:blur(14px);white-space:nowrap;transition:all .3s}
#vanta-root .nb.tl{border-color:var(--tl);color:var(--tl);background:rgba(0,80,70,.2)}
#vanta-root .nb.am{border-color:var(--am);color:var(--am);background:rgba(90,40,0,.2)}
#vanta-root .nb.gr{border-color:var(--gr);color:var(--gr);background:rgba(0,60,30,.2)}
#vanta-root .nb.pu{border-color:var(--pu);color:var(--pu);background:rgba(60,0,110,.2)}
#vanta-root .nl{font-family:var(--disp);font-size:6.5px;color:var(--dim);letter-spacing:2px}
#vanta-root .ndot{width:4px;height:4px;border-radius:50%;background:var(--gr);box-shadow:0 0 5px var(--gr);animation:vhdp 1.5s ease-in-out infinite}
#vanta-root .ndot.am{background:var(--am);box-shadow:0 0 5px var(--am)}
#vanta-root #pl{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);display:flex;align-items:center;z-index:25;white-space:nowrap}
#vanta-root .ps{display:flex;flex-direction:column;align-items:center;gap:2px}
#vanta-root .pb{padding:3px 7px;border:1px solid rgba(0,212,255,.28);font-family:var(--disp);font-size:8px;color:var(--dim);background:rgba(0,15,40,.22);backdrop-filter:blur(12px);letter-spacing:1px;transition:all .3s}
#vanta-root .pb.dn{border-color:rgba(0,255,136,.5);color:var(--gr);background:rgba(0,30,15,.2)}
#vanta-root .pb.ac{border-color:var(--c);color:var(--c);background:rgba(0,40,80,.2);box-shadow:0 0 8px rgba(0,212,255,.3)}
#vanta-root .pb.dm2{border-color:rgba(0,180,255,.1);color:rgba(0,180,255,.25)}
#vanta-root .psl{font-size:6.5px;color:var(--dim);letter-spacing:1px;font-family:var(--disp)}
#vanta-root .par{color:rgba(0,212,255,.38);font-size:13px;padding:0 2px;margin-bottom:10px;font-family:var(--disp)}
#vanta-root #pllb{position:absolute;bottom:3px;left:50%;transform:translateX(-50%);font-family:var(--disp);font-size:7px;letter-spacing:5px;color:var(--dim)}
#vanta-root #cb{position:absolute;bottom:0;left:0;right:0;height:48px;background:rgba(2,8,22,.98);border-top:1px solid var(--border);display:flex;align-items:center;padding:0 12px;gap:10px;z-index:300}
#vanta-root #chl{color:var(--c);font-family:var(--disp);font-size:10px;letter-spacing:2px;white-space:nowrap;animation:vhlp 2.5s ease-in-out infinite}
#vanta-root #chi{flex:1;background:transparent;border:none;border-bottom:1px solid rgba(0,212,255,.2);color:var(--txt);font-family:var(--mono);font-size:11px;padding:4px 0;outline:none;letter-spacing:.5px}
#vanta-root #chi::placeholder{color:var(--dim)}
#vanta-root #chi:focus{border-bottom-color:var(--c)}
#vanta-root .sis{display:flex;border-left:1px solid var(--border);border-right:1px solid var(--border);padding:0 8px}
#vanta-root .si{padding:0 6px;font-size:9px;color:var(--dim);letter-spacing:1px;border-right:1px solid rgba(0,180,255,.1);white-space:nowrap}
#vanta-root .si:last-child{border-right:none}
#vanta-root .sg{color:var(--gr)}#vanta-root .sa{color:var(--am)}#vanta-root .sc{color:var(--c)}
#vanta-root #micbtn{padding:6px 10px;border:1px solid rgba(0,212,255,.3);background:transparent;color:var(--dim);font-size:14px;cursor:pointer;transition:all .3s}
#vanta-root #sndbtn{padding:6px 16px;border:1px solid var(--c);background:rgba(0,212,255,.08);color:var(--c);font-family:var(--disp);font-size:9px;letter-spacing:3px;cursor:pointer;transition:all .25s}
#vanta-root #sndbtn:hover{background:rgba(0,212,255,.18);box-shadow:0 0 16px rgba(0,212,255,.35)}
#vanta-root.sp #orb{animation:vhobf 1s ease-in-out infinite}
@keyframes vhobf{0%,100%{box-shadow:0 0 60px rgba(0,220,255,1),0 0 120px rgba(0,200,255,.8),0 0 240px rgba(0,160,255,.5),inset 0 0 38px rgba(0,125,230,.55)}50%{box-shadow:0 0 80px rgba(80,235,255,1),0 0 160px rgba(40,215,255,.9),0 0 340px rgba(0,185,255,.6),inset 0 0 55px rgba(0,155,248,.72)}}
#vanta-root.sa #orb{animation:vhoba 2s ease-in-out infinite}
@keyframes vhoba{0%,100%{box-shadow:0 0 35px rgba(255,149,0,.85),0 0 70px rgba(255,100,0,.55),inset 0 0 28px rgba(155,55,0,.45)}50%{box-shadow:0 0 52px rgba(255,175,0,.98),0 0 105px rgba(255,125,0,.75),inset 0 0 42px rgba(185,72,0,.58)}}
/* Voice states (Fix 2) */
#vanta-root.vstandby #orb{filter:saturate(.55) brightness(.7);animation:vhstandby 5s ease-in-out infinite}
@keyframes vhstandby{0%,100%{box-shadow:0 0 18px rgba(0,110,200,.4),inset 0 0 16px rgba(0,55,140,.3)}50%{box-shadow:0 0 30px rgba(0,140,220,.5),inset 0 0 22px rgba(0,70,160,.35)}}
#vanta-root.vstandby #og{opacity:.4}
#vanta-root.vwake #orb{animation:vhwake .5s ease-out forwards;filter:brightness(1.6)}
@keyframes vhwake{0%{box-shadow:0 0 90px #fff,0 0 180px rgba(255,255,255,.9),inset 0 0 55px #fff}100%{box-shadow:0 0 45px rgba(0,210,255,.9),0 0 90px rgba(0,180,255,.6),inset 0 0 30px rgba(0,120,220,.5)}}
#vanta-root.vrec #orb{animation:vhobf 1s ease-in-out infinite}
#vanta-root.vspeak #orb{animation:vhob 1.1s ease-in-out infinite}
#vanta-root.vspeak .pr{animation:vhpe 1.3s ease-out infinite}
`}</style>
  );
}
