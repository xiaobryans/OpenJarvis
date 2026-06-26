/**
 * NeuralCommandCenter.tsx — barrel re-export.
 *
 * Split into focused modules:
 *   ncc-types.ts        — TypeScript types and interfaces
 *   ncc-primitives.tsx  — dot, CommandPanel, StatusMiniCard, CommandInputStrip
 *   ncc-desktop.tsx     — DesktopCommandCenter (three-column layout)
 *   ncc-mobile.tsx      — MobileCommandCenter (stacked layout)
 *
 * All callers (JarvisCockpitPage.tsx etc.) continue importing from this file.
 */

export type {
  StatusDot,
  TurnPhase,
  ConnectorInfo,
  MemoryStatus,
  RoutingStatus,
  RegistryStatus,
  FinalSmokeStatus,
  SigningStatus,
  CompletionScore,
  NccCoreProps,
  NccProps,
} from './ncc-types';

export { dot, CommandPanel, StatusMiniCard, CommandInputStrip } from './ncc-primitives';

export type { NccLayoutProps } from './ncc-desktop';
export { DesktopCommandCenter } from './ncc-desktop';

export { MobileCommandCenter } from './ncc-mobile';
