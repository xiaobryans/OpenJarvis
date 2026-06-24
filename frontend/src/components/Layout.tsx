import { Outlet, useLocation } from 'react-router';
import { VoiceOverlay } from './VoiceOverlay';

// Layout is now a minimal wrapper — the Sidebar has been replaced by the
// JarvisCommandCenter HUD (JarvisCockpitPage). All navigation happens through
// compact floating panels and modal overlays on the main orb page.
// Legacy routes remain reachable via panel overlays or deep-links.

export function Layout() {
  const location = useLocation();
  // Suppress the floating VoiceOverlay mic button on the cockpit page (index route /).
  // Voice is PARKED/UNSAFE in the cockpit; the floating mic would overlap cockpit content.
  const isCockpit = location.pathname === '/';

  return (
    <div className="flex flex-col h-full w-full overflow-hidden relative">
      <main className="flex-1 flex flex-col min-w-0 h-full relative overflow-hidden" style={{ background: 'transparent' }}>
        <Outlet />
      </main>
      {!isCockpit && <VoiceOverlay />}
    </div>
  );
}
