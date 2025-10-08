# Draft-Buddy UI/UX Improvement Plan (Roadmap)

Purpose: Make the app feel more fluid, modern, and natural — both visually and functionally — while staying lightweight and consistent across desktop and mobile (Kivy).

The items below are grouped by phases to enable incremental delivery. Each task has clear acceptance criteria. Prioritize top to bottom within each phase.


## Phase 0 — Baseline polish (quick wins)
- Unify spacing and padding
  - Action: Audit all layouts in ui.kv to use dp() consistently (8/12/16 spacing scale). Prefer spacing: dp(8–12), padding: dp(10–16).
  - Files: ui.kv
  - Acceptance: No mixed px values; Scan shows dp() everywhere; visual rhythm is consistent.

- Consistent typography
  - Action: Define a small set of font sizes and weights for titles, section headers, body, captions; apply via reusable classes in kv (e.g., <TitleLabel@Label>, <HeaderLabel@Label>, <BodyLabel@Label>).
  - Files: ui.kv
  - Acceptance: All Labels use one of the typography classes; no inline font_size sprinkled ad-hoc.

- Button look and feel
  - Action: Create <PrimaryButton@Button> and <SecondaryButton@Button> with consistent height, min_width, padding, and background_color/normal/down images or canvas instructions.
  - Files: ui.kv
  - Acceptance: No raw Button used for primary flows; tap target >= dp(44) height.

- Input affordances and validation
  - Action: Ensure TextInput fields have hint_text, proper multiline False where relevant, and on_enter triggers focus navigation or submit; trim leading spaces.
  - Files: ui.kv, main.py (focus_next if needed)
  - Acceptance: Forms are keyboard-friendly; invalid states show feedback.


## Phase 1 — Navigation and layout coherence
- Bottom navigation consistency
  - Action: Convert repeated footer nav rows into a reusable widget (<BottomNav@BoxLayout>) with equal-width buttons and active state, to keep screens consistent.
  - Files: ui.kv
  - Acceptance: All main screens share the same footer; current screen’s button shows active state.

- Screen transitions
  - Action: Replace NoTransition with SlideTransition or FadeTransition where appropriate; keep transition duration short (~0.15–0.2s) for fluid feel.
  - Files: main.py
  - Acceptance: Navigations animate subtly; no jarring jumps.

- Safe areas and scroll behavior
  - Action: Ensure ScrollView content has proper size_hint_y and minimum_height to avoid clipped or bouncy content; ensure headers are fixed and content scrolls.
  - Files: ui.kv
  - Acceptance: Long lists scroll smoothly; headers toolbars remain visible.


## Phase 2 — Visual theme and feedback
- Light/Dark theme scaffold
  - Action: Define an AppTheme (Python or kv) with color tokens: primary, secondary, surface, on_surface, background, success, warning, error. Bind Button/Label colors to theme.
  - Files: main.py (theme dict + properties), ui.kv (use theme refs)
  - Acceptance: Single place to change colors; all widgets update without per-widget edits.

- Visual feedback states
  - Action: Use canvas.before to draw rounded rectangles and pressed/disabled states for PrimaryButton; add hover states on desktop (Window.mouse_pos) when available.
  - Files: ui.kv, main.py (if hover handlers needed)
  - Acceptance: Buttons clearly indicate hover/press/disabled.

- Non-blocking toasts/snackbars
  - Action: Implement lightweight toast/snackbar component for confirmations instead of intrusive popups where appropriate (e.g., “Player saved”).
  - Files: ui.kv (<Toast@FloatLayout>), main.py (helper to show/hide)
  - Acceptance: Short messages appear at bottom, auto-dismiss; popups only for decisions.


## Phase 3 — Information architecture and density
- Lists and cards
  - Action: For players/events lists, create a <ListItem@BoxLayout> with title, subtitle, trailing actions (e.g., start, edit, delete), and consistent height (dp(56–64)). Optionally use a subtle card background.
  - Files: ui.kv
  - Acceptance: Lists are scannable; actions are consistent and discoverable.

- Empty states
  - Action: Add empty state views with friendly guidance and a primary action when lists are empty (e.g., “No players yet — Add your first player”).
  - Files: ui.kv, main.py (conditional rendering)
  - Acceptance: Empty lists don’t look broken; they invite action.

- Progressive disclosure
  - Action: Hide advanced options behind a chevron expander or an “Advanced” section to reduce clutter on first sight.
  - Files: ui.kv
  - Acceptance: Primary tasks are front-and-center; advanced available but tucked away.


## Phase 4 — Motion and micro-interactions
- Subtle micro-animations
  - Action: Animate list item addition/removal, timer state changes (start/pause), and round transitions using Animation in Kivy (duration 0.15–0.25s, ease_in_out).
  - Files: main.py, ui.kv, timer.py
  - Acceptance: Animations feel quick and purposeful; no lag.

- Timer visual improvements
  - Action: Use a progress ring/bar synced to DraftTimer; color shift near thresholds (e.g., warning at 15s, danger at 5s). Gentle tick and optional vibration (if platform supports).
  - Files: timer.py, ui.kv, assets (reuse existing sounds)
  - Acceptance: Visual timer communicates time left without reading numbers.


## Phase 5 — Accessibility and responsiveness
- Accessibility basics
  - Action: Ensure contrast ratios are acceptable (WCAG-ish), minimum touch targets dp(44), larger type size option via an App setting.
  - Files: ui.kv, main.py
  - Acceptance: App is usable on small screens and by users needing larger text.

- Responsive layout
  - Action: Use size classes (compact/medium/expanded) based on Window.size; adjust paddings, grid columns, and typography scale accordingly.
  - Files: main.py (size class computation), ui.kv (binds)
  - Acceptance: Desktop/tablet show more columns; phone stays single column.


## Phase 6 — Structure, code health, and performance
- Separate kv from main.py
  - Action: Move the inlined KV (if any) from main.py into ui.kv (or multiple kv files) to centralize styling and components.
  - Files: main.py, ui.kv
  - Acceptance: No large KV strings inside Python; easier to maintain.

- Reusable components library
  - Action: Define and reuse ui components: TitleBar, BottomNav, ListItem, PrimaryButton, Section, FormRow.
  - Files: ui.kv
  - Acceptance: Fewer duplicated patterns across screens.

- Performance hygiene
  - Action: Avoid heavy canvas shadows; cache backgrounds; throttle expensive layout passes; defer DB/IO from UI thread (Clock.schedule_once, threading if needed).
  - Files: main.py, db.py
  - Acceptance: Stable 60 fps feeling on typical devices.


## Nice-to-haves
- Haptics on mobile
  - Action: Integrate plyer to trigger vibration on key interactions (timer thresholds, match start), with a user toggle.

- Theming presets
  - Action: Provide two color presets (Classic, High-contrast) selectable in Settings; persist preference.


## Concrete tasks (actionable checklist)
- [ ] Create Theme class or App properties: colors (primary, on_primary, surface, on_surface, bg, success, warning, error). Wire to kv via app.theme.* or root.theme.*.
- [ ] Define typography styles: <TitleLabel@Label>, <HeaderLabel@Label>, <BodyLabel@Label>, <CaptionLabel@Label> with font_size dp values and bold where needed.
- [ ] Define buttons: <PrimaryButton@Button>, <SecondaryButton@Button> with height dp(48), padding dp(12, 10), rounded rect via canvas.before, state colors.
- [ ] Build <BottomNav@BoxLayout> reusable widget; replace footer bars in Players, Events, League, Bingo, DraftTimer screens.
- [ ] Switch ScreenManager to SlideTransition(duration=0.18) or FadeTransition where appropriate.
- [ ] Add Toast helper: ui.kv component + App.show_toast(msg, timeout=2.0).
- [ ] Implement empty states for Players and Events lists with icon/text/button.
- [ ] Create <ListItem@BoxLayout> and retrofit players/events items with title/subtitle/actions.
- [ ] Improve DraftTimer visualization: progress bar/ring bound to remaining time; sound cues reuse assets/tick.wav, warning color.
- [ ] Add size classes (compact/medium/expanded) and bind paddings/columns accordingly.
- [ ] Add setting for Large Text; scale typography tokens by 1.2x when enabled.
- [ ] Review all TextInputs for proper hint_text, multiline=False, and enter/next behavior.
- [ ] Replace remaining inline px spacing with dp().
- [ ] Ensure contrast: verify color pairs; tweak theme if needed.
- [ ] Add hover feedback on desktop for buttons and list items (optional).


## Notes on implementation in this repo
- main.py already enforces a portrait-like window on desktop — good for testing phone proportions; keep it but make it opt-out via a command-line flag or an app setting later.
- ui.kv already standardizes Button alignment; extend it into concrete Primary/Secondary styles instead of modifying each Button inline.
- timer.py: expose remaining_fraction property in DraftTimer to bind progress UI; emit events at thresholds (15s, 5s) for color/sound.
- db operations (db.py) should remain off the UI thread when loading/refreshing large lists; use Clock.schedule_once to keep UI responsive.


## Acceptance for the whole initiative
- Visual: UI looks consistent and modern, with coherent spacing, typography, and colors; key actions stand out.
- Functional: Navigation is consistent and animated subtly; lists are scannable with empty states; timer conveys urgency visually.
- Usability: Minimum touch targets achieved; larger text mode available; dark mode scaffold prepared.
- Maintainability: Reusable components defined; kv separated and decluttered; color and type tokens centralized.
