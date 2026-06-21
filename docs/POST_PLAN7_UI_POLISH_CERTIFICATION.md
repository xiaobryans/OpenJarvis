# Post-Plan-7 UI Polish Sprint — Certification

**Verdict:** POST_PLAN7_UI_POLISH_ACCEPT_PENDING_REVIEW

---

## Scope

Post-Plan-7C UI / Polish / Onboarding Sprint.
Visual system upgrade, cockpit enhancements, onboarding, connector status display,
approval UX improvements, mobile polish, and error/loading/empty state improvements.

**Not in scope (confirmed not started):**
- Plan 8 Trusted Delegation
- Final hostile/lazy-user cutover certification
- Apple signing (enrollment pending)
- Voice (US13) — parked/unsafe
- New sensitive billing/deletion/security authority

---

## Branch and Commit Context

- **Branch:** `localhost-get-tool`
- **Remote:** `fork/localhost-get-tool`
- **HEAD before sprint:** `b155fe8b`

---

## Changed Files

| File | Change |
|------|--------|
| `frontend/src/index.css` | Added magenta accent tokens, semantic status tokens (`--color-status-live/blocked/parked/pending`), `.glass-panel`, `.neon-chip*`, `.cockpit-scan`, `.status-dot-*` CSS classes |
| `frontend/src/components/ConnectorStatusBar.tsx` | **New** — horizontal HUD strip showing GitHub (live/blocked via API), Gmail/Calendar/Slack/Telegram (blocked), Voice (parked), Apple Signing (pending), Plan 8 (not started) |
| `frontend/src/components/Layout.tsx` | Integrated `ConnectorStatusBar` as persistent strip; improved backend offline banner with glow dot |
| `frontend/src/components/Sidebar/Sidebar.tsx` | Renamed "Mission Control" → "Cockpit", "Get Started" → "Onboarding", "Data Sources" → "Connectors"; added "4 blocked" badge on Connectors nav item |
| `frontend/src/pages/MissionControlPage.tsx` | Replaced plain System Health panel with glassmorphism "JARVIS COCKPIT" panel (cockpit-scan animation, HUD reticle, neon chips); upgraded No-Gap Readiness panel with Plan 8 / Apple Signing status; improved approval queue cards with risk header strip + full approve/deny buttons |
| `frontend/src/pages/GetStartedPage.tsx` | Transformed from install guide into full onboarding/capability tour: hero section, live capabilities grid, blocked connectors, approval flow explainer, mobile/desktop continuity, honest limitations, roadmap (Plan 8 / final cutover) |
| `frontend/src/pages/MobilePage.tsx` | Visual upgrade: glass-panel cards with backdrop-blur, glow header, HUD monospace labels; added Connector & Gate Status card showing all connector/gate states |
| `frontend/src/components/Jarvis/JarvisHomePage.tsx` | Added command example chips and "Voice: parked/unsafe · GitHub LIVE" status footer |
| `docs/POST_PLAN7_UI_POLISH_CERTIFICATION.md` | **This file** |

---

## Desktop UI Changes

- **Layout**: persistent `ConnectorStatusBar` strip below health banner showing all connector/gate states at all times
- **Sidebar**: Cockpit nav item renamed + Connectors badge showing "4 blocked" (Gmail/Calendar/Slack/Telegram)
- **Cockpit (MissionControlPage)**: glassmorphism JARVIS COCKPIT header panel with cockpit-scan animation, all runtime/connector/gate status chips, certification gates with Plan 8 / Apple Signing status
- **Approval Queue**: risk-color header strip, full-width approve/deny buttons, description/summary shown; empty state explains how approvals work
- **GetStartedPage → Onboarding**: complete capability tour with live/blocked/parked status rows, how approvals work, mobile continuity, roadmap
- **JarvisHomePage**: command example chips, status footer (Voice parked, GitHub LIVE)

## Mobile UI Changes

- **MobilePage header**: glassmorphism card with neon glow, HUD MOBILE label, accent refresh button
- **Cards**: upgraded to `glass-panel` style (backdrop-blur, gradient, glow shadow)
- **Connector & Gate Status card**: new section at bottom showing all 9 connector/gate states (GitHub LIVE, Gmail/Calendar/Slack/Telegram blocked, Voice parked, Apple Signing pending, Plan 8 not started, Final Cutover not started)
- **ConnectorStatusBar**: visible in mobile PWA via Layout (same as desktop)
- Capability-equivalent to desktop — no features hidden behind impossible navigation

## Onboarding Changes

- `GetStartedPage` fully transformed
- Hero: what Jarvis is, backend health indicator, "Open Jarvis" CTA
- "What's Live Now" section: GitHub, Memory OS, Mission Control, AWS Runtime, Tools/Skills, Approval System — all as live capability cards with examples
- "What Needs Credentials" section: all 6 blocked/parked items with honest status rows
- "How Approvals Work" section: 5-step flow explainer
- "Mobile & Desktop Continuity" section
- "Honest Limitations" section: explicit list of what not to trust yet
- "Roadmap" section: Plan 8 (not started), Voice sprint, Apple Signing, Gmail/Calendar, Final Cutover (not started)
- Skippable (dismiss button), revisitable via Onboarding nav link

## Connector / Status UX Changes

- `ConnectorStatusBar`: always-visible horizontal strip at top of all pages
  - GitHub: live/blocked via `/v1/connectors` API; auto-refreshes every 60s
  - Gmail: BLOCKED — OAuth
  - Calendar: BLOCKED — OAuth
  - Slack: BLOCKED — token
  - Telegram: BLOCKED — token
  - Voice: PARKED
  - Apple Signing: PENDING
  - Plan 8: NOT STARTED
- Connectors nav item in sidebar: "4 blocked" amber badge
- Cockpit panel: shows all connector/system states in neon chips

## Approval / Safety UX Changes

- Approval queue cards now show risk-level header strip with color-coded risk label
- Task description/summary shown in card body
- Approve/Deny buttons are full-width with clear styling (green/red with matching border+background)
- Empty state explains why approvals exist and what Jarvis will ask for
- No new sensitive powers granted — all hard gates remain in place
- Plan 8 "NOT STARTED" label shown in both Cockpit panel and Onboarding
- Destructive/sensitive actions blocked note shown in Onboarding limitations section

## Visual Design Changes

- New CSS tokens: `--color-accent-magenta`, `--color-accent-magenta-subtle`, `--color-status-live/blocked/parked/pending`
- New CSS classes: `.glass-panel`, `.neon-chip`, `.neon-chip-live/blocked/parked/pending`, `.cockpit-scan`, `.status-dot-live/blocked/parked`
- Glass morphism cards (backdrop-blur, gradient border, subtle glow) throughout cockpit and mobile
- Cockpit scan-line animation on JARVIS COCKPIT header
- HUD reticle in cockpit header
- Neon glow status chips for live indicators
- Color-coded risk strips on approval cards
- Command example pills on voice home screen

---

## Tests / Builds Run

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | ✅ 0 errors |
| `npm test -- --run` (vitest) | ✅ 19/19 tests pass |
| `git diff --check` | ✅ clean (no whitespace errors) |
| Secret scan (rg on changed files) | ✅ no credential values — only UI label strings |
| Tauri desktop build | ❌ Not run — Apple signing blocked, Tauri build requires enrolled Developer ID. Not feasible in this sprint. |
| Mobile PWA build | [ASSUMED] — not separately invoked; TypeScript clean and same codebase as desktop web build |

Note: Tauri desktop build not performed because Apple enrollment is pending (BLOCKED_APPLE_ENROLLMENT_PENDING). The frontend is TypeScript-clean and vite-buildable; Tauri packaging is the blocker, not the UI code.

---

## Remaining Blockers

| Item | Status |
|------|--------|
| Apple signing / Auto-updater | BLOCKED — Apple Developer enrollment pending |
| US13 Voice | PARKED / UNSAFE — dedicated safety sprint required |
| Gmail OAuth | BLOCKED — needs Google Cloud OAuth credentials |
| Calendar OAuth | BLOCKED — needs Google Cloud OAuth credentials |
| Slack token | BLOCKED — needs xoxp user token |
| Telegram token | BLOCKED — needs bot token |
| Plan 8 Trusted Delegation | NOT STARTED — begins after Bryan review |
| Final hostile/lazy-user cutover certification | NOT STARTED |

---

## Confirmation

- ✅ Plan 8 was NOT started in this sprint
- ✅ No new sensitive/billing/deletion authority was added
- ✅ Final cutover certification is still not passed
- ✅ All blocked connector states are shown honestly in the UI (not faked as live)
- ✅ Voice parked status is displayed, not hidden
- ✅ Apple signing pending status is displayed, not hidden

---

## Plan 8 Eligibility

Plan 8 (Trusted Delegation / Sensitive Authority Expansion) may begin after:
1. Bryan reviews this UI polish sprint and provides explicit "Plan 8 may begin" approval
2. Final hostile/lazy-user cutover certification is planned (separate sprint)

Plan 8 will NOT start automatically from this commit.
