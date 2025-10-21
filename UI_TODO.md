# Draft-Buddy UI/UX TODO — Fresh List

Updated: 2025-10-21 08:52 (local)

Goal: Make Draft-Buddy feel fast, focused, and friendly on phones and desktops, without bloating the codebase. This list replaces the previous roadmap and removes items that are already implemented (e.g., BottomNav and in-app toasts).


## Immediate (quick wins)
- Tighten spacing and alignment
  - Action: Standardize spacing/padding to a simple scale using dp() (8/12/16). Remove stray px literals.
  - Files: ui.kv
  - Acceptance: Visual rhythm feels consistent; quick scan finds only dp(...).

- Typography tokens
  - Action: Add minimal text styles via reusable kv rules (Title, Subtitle, Body, Caption) and apply to major screens.
  - Files: ui.kv
  - Acceptance: No ad-hoc font_size on Labels where tokens apply; headings are visually distinct.

- Primary/Secondary button styles
  - Action: Provide consistent button height, padding, and rounded background via canvas; keep colors readable in light backgrounds.
  - Files: ui.kv
  - Acceptance: Key actions look consistent; tap targets ≥ dp(44) high.

- Form ergonomics
  - Action: Ensure TextInput fields have hint_text, proper multiline usage, and enter/next flow; trim leading/trailing spaces before save.
  - Files: ui.kv, main.py
  - Acceptance: Adding players/events is fast from keyboard or touch; no accidental whitespace persists.

- Empty states where lists can be empty
  - Action: Provide friendly message and primary action when Players/Events have no items.
  - Files: ui.kv, main.py
  - Acceptance: First-time experience feels guided, not broken.


## Near‑term (visual clarity and navigation)
- Active state styling for BottomNav
  - Action: Improve visual distinction for the current tab and ensure adequate contrast.
  - Files: ui.kv
  - Acceptance: Current tab is clearly highlighted on phone and desktop.

- Subtle screen transitions
  - Action: Use very short SlideTransition or FadeTransition where navigation benefits from context.
  - Files: main.py
  - Acceptance: Navigations feel fluid but snappy (< 0.2s).

- Scroll behavior and safe areas
  - Action: Verify ScrollView content sizing to prevent clipping; keep headers/toolbars fixed where appropriate.
  - Files: ui.kv
  - Acceptance: Long lists scroll smoothly; headers do not jitter.

- Timer visualization improvements
  - Action: Add a simple progress bar/ring bound to remaining time; change color near thresholds (15s warning, 5s danger). Reuse assets/tick.wav.
  - Files: timer.py, ui.kv, assets
  - Acceptance: Time pressure is readable at a glance, even without reading numbers.


## Accessibility and responsiveness
- Contrast and touch targets
  - Action: Ensure minimum 4.5:1 for text on backgrounds where feasible; keep interactive elements ≥ dp(44).
  - Files: ui.kv
  - Acceptance: Basic WCAG-ish contrast; comfortably tappable controls.

- Large text option
  - Action: App setting that scales typography tokens ~1.2x.
  - Files: main.py, ui.kv
  - Acceptance: Users can toggle larger text and see it applied immediately.

- Size classes
  - Action: Define compact/medium/expanded based on Window.size and adjust paddings/columns accordingly.
  - Files: main.py, ui.kv
  - Acceptance: Desktop/tablet layouts show more content without crowding; phones remain single-column.


## Code health and performance
- Reusable UI bits
  - Action: Extract common widgets (TitleBar, ListItem, Section row) to reduce duplication.
  - Files: ui.kv
  - Acceptance: Fewer repeated layouts; easier maintenance.

- Performance hygiene
  - Action: Avoid heavy canvas effects; keep DB/IO off UI thread; throttle expensive layout passes where possible.
  - Files: main.py, db.py
  - Acceptance: Smooth interactions on modest Android devices.


## Backlog / Ideas (nice to have)
- Haptics on mobile via plyer (toggle in settings)
- High-contrast theme preset (switchable)
- Hover feedback on desktop for buttons/list items
- Lightweight snackbar variant for longer messages
- Simple onboarding tip on first launch


## Acceptance for this iteration
- Visual: Consistent spacing, typography tokens, and button styles across key screens.
- Functional: Empty states in Players/Events; quick, low-latency transitions; clearer nav active state.
- Usability: Adequate contrast and touch targets; optional large text mode.
- Maintainability: Shared UI components extracted; dp() used consistently.
