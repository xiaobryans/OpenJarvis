// VantaPermissions — one-time first-launch screen asking Bryan to grant the
// macOS permissions VANTA needs (mic for voice, Accessibility + Input Monitoring
// for the global hotkey). Dismissed permanently via localStorage.

import React from 'react';

const SEEN_KEY = 'vanta-permissions-seen';

// Deep link straight to System Settings → Privacy & Security.
const PRIVACY_URL = 'x-apple.systempreferences:com.apple.preference.security?Privacy';
const PANES: { label: string; why: string; url: string }[] = [
  { label: 'Microphone', why: 'voice wake word + conversation', url: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone' },
  { label: 'Accessibility', why: 'Cmd+Shift+V global hotkey', url: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility' },
  { label: 'Input Monitoring', why: 'detecting the hotkey system-wide', url: 'x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent' },
];

export function permissionsSeen(): boolean {
  try { return localStorage.getItem(SEEN_KEY) === 'true'; } catch { return false; }
}

function openSettings(url: string): void {
  try { window.open(url, '_blank'); } catch { /* webview may block; instructions still shown */ }
}

export function VantaPermissions({ open, onClose }: { open: boolean; onClose: () => void }): React.ReactElement | null {
  if (!open) return null;
  const dismiss = () => {
    try { localStorage.setItem(SEEN_KEY, 'true'); } catch { /* ignore */ }
    onClose();
  };
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 600, display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(1,5,12,0.7)', backdropFilter: 'blur(4px)', fontFamily: "'Space Mono',monospace",
    }}>
      <div style={{
        width: 'min(560px, 90%)', background: 'rgba(4,16,40,0.95)', border: '1px solid rgba(0,212,255,0.25)',
        borderRadius: 10, padding: '22px 26px', boxShadow: '0 0 40px rgba(0,200,255,0.12), 0 20px 60px rgba(0,0,0,0.6)',
      }}>
        <div style={{ fontFamily: "'Exo 2',sans-serif", fontWeight: 900, fontSize: 18, letterSpacing: '5px', color: '#e8f8ff', textShadow: '0 0 18px rgba(0,212,255,0.4)', marginBottom: 4 }}>
          ONE-TIME SETUP
        </div>
        <div style={{ fontSize: 11, color: 'rgba(142,200,232,0.7)', lineHeight: 1.6, marginBottom: 16 }}>
          VANTA needs a few macOS permissions to run hands-free. Grant these once in
          System Settings → Privacy &amp; Security, then you're set.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
          {PANES.map((p) => (
            <div key={p.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '8px 12px', border: '1px solid rgba(0,212,255,0.12)', borderRadius: 6, background: 'rgba(0,212,255,0.03)' }}>
              <div>
                <div style={{ fontSize: 12, color: '#00d4ff', letterSpacing: '1px' }}>{p.label}</div>
                <div style={{ fontSize: 9.5, color: 'rgba(142,200,232,0.55)' }}>for {p.why}</div>
              </div>
              <button onClick={() => openSettings(p.url)} style={{ padding: '5px 10px', border: '1px solid rgba(0,212,255,0.4)', background: 'rgba(0,212,255,0.08)', color: '#00d4ff', fontSize: 9, letterSpacing: '1px', cursor: 'pointer', borderRadius: 4, whiteSpace: 'nowrap' }}>
                Open
              </button>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'space-between' }}>
          <button onClick={() => openSettings(PRIVACY_URL)} style={{ flex: 1, padding: '9px 14px', border: '1px solid #00d4ff', background: 'rgba(0,212,255,0.12)', color: '#00d4ff', fontFamily: "'Exo 2',sans-serif", fontSize: 10, letterSpacing: '3px', cursor: 'pointer', borderRadius: 5 }}>
            OPEN SYSTEM SETTINGS
          </button>
          <button onClick={dismiss} style={{ padding: '9px 16px', border: '1px solid rgba(0,212,255,0.2)', background: 'transparent', color: 'rgba(142,200,232,0.7)', fontFamily: "'Exo 2',sans-serif", fontSize: 10, letterSpacing: '2px', cursor: 'pointer', borderRadius: 5 }}>
            DONE
          </button>
        </div>
      </div>
    </div>
  );
}
