import { Outlet } from 'react-router';
import { VoiceOverlay } from './VoiceOverlay';

// Layout is now a minimal wrapper — the Sidebar has been replaced by the
// JarvisCommandCenter HUD (JarvisCockpitPage). All navigation happens through
// compact floating panels and modal overlays on the main orb page.
// Legacy routes remain reachable via panel overlays or deep-links.

export function Layout() {
  return (
    <div className="flex flex-col h-full w-full overflow-hidden relative">
      <main className="flex-1 flex flex-col min-w-0 h-full relative overflow-hidden" style={{ background: 'transparent' }}>
        <Outlet />
      </main>
      <VoiceOverlay />
    </div>
  );
}
