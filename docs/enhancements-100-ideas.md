# DesktopNote — 100 Enhancement Ideas (P0 / P1 / P2)

> Brainstormed with the web-design "taste" vocabulary translated to a native Win32 + Direct2D + RichEdit
> desktop sticky-note app. Priorities: **P0** = core-experience must, high value, low ambiguity; **P1** = clearly
> good, medium lift; **P2** = polish / future / nice-to-have.
> Grounded in the real stack: per-note windows, window modes (普通/置顶/嵌入桌面/穿透/锁定/贴边自动隐藏),
> edge docking collapse tabs, custom toolbar, RichEdit RTF content, tray icon, global hotkeys for quick capture.

---

## A. 编辑与文本 (Editing & Text)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 1 | Paste plain-text toggle (Ctrl+Shift+V) strips RTF formatting on paste | P0 | Respect source formatting otherwise |
| 2 | Smart auto-list: typing `- ` or `1. ` at line start begins a real list | P1 | RichEdit numbering |
| 3 | Trailing-space + Enter soft-break: Enter inside a line inserts single newline, not a paragraph | P1 | |
| 4 | Find within note (Ctrl+F) with highlighted matches and match counter | P1 | |
| 5 | Character/word/line count in a small status footer (toggle from context menu) | P0 | |
| 6 | Auto-save indicator: subtle "已保存 HH:MM" that fades, never a modal | P0 | |
| 7 | Undo stack survives window hide/show (don't drop undo on blur) | P1 | |
| 8 | Inline image paste (screenshot) stored as base64 RTF, visible in note | P2 | RTF complexity, size limit |
| 9 | Smart URL detection: paste a URL as a clickable link | P1 | |
| 10 | Markdown-lite underline/slash shortcuts (select word → `**` bolds) | P2 | |
| 11 | Tab key indents / Shift+Tab outdents in a list; Tab inserts a real tab in plain text | P1 | |
| 12 | "Insert current date/time" (Ctrl+; / Ctrl+Shift+;) with locale format | P1 | common note need |
| 13 | Word-wrap vs. horizontal-scroll toggle | P2 | |
| 14 | Live spellcheck underline (Windows spellcheck API) | P2 | |
| 15 | @mention-style inline tag or #hashtag highlight (visual only, no semantics) | P2 | |
| 16 | Font size quick-steps: Ctrl+= / Ctrl+- adjust size without opening toolbar | P1 | |
| 17 | Bold/italic/underline via keyboard (Ctrl+B/I/U) without toolbar | P0 | |
| 18 | Paste paste-to-match-style: inherit the style of the paragraph you paste into | P2 | |
| 19 | Select-all + typing replaces selection (native already), confirm it works with custom caret | P1 | caret correctness after fix |
| 20 | Long-note pagination / line limit warning before perf degrades | P2 | |

## B. 外观与主题 (Appearance & Themes)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 21 | A real palette system: 6 curated note themes (contrast-safe) instead of raw color pickers | P0 | one accent per note, WCAG AA ink on bg |
| 22 | Respect `prefers-color-scheme`: optional auto light/dark default surfaces | P1 | System dark detection |
| 23 | Per-note accent color locked + used consistently on tab, accent bar, caret | P1 | Color-consistency lock |
| 24 | Matching rounded-corner radius scale across tab / toolbar / badges (one radius system) | P0 | shape-consistency lock |
| 25 | Gram, blur-minimal "paper" texture: subtle top-lit gradient, no harsh solids | P2 | |
| 26 | Font stack default to a non-slop system font (雅黑/系统) with anti-aliasing tuned | P1 | |
| 27 | Drop the pure-white & pure-black bg/text combos; use off-white + near-ink | P1 | AI/slop colour fix |
| 28 | Focused vs unfocused appearance: clear but calm de-emphasis when not active | P1 | hierarchy |
| 29 | Toolbar adaptive density: compact when wide, wraps gracefully when narrow | P1 | |
| 30 | Themed status badges (lock/pin/desktop) coloured by state, not all white-on-grey | P1 | |
| 31 | Custom accent applied to the collapsed dock tab handle so it reads at a glance | P0 | |
| 32 | Editor background follows note alpha but text stays full-contrast at all times | P1 | legibility |
| 33 | Light and dark note skins both shipped + a quick toggle per note | P2 | |
| 34 | Letter-spacing control (rare, but a taste lever) | P2 | |
| 35 | Title / header bleed: first line as a slightly emphatic "title" with auto-detect | P2 | |
| 36 | Soft drop shadow on floating notes (real DWM shadow, tinted, no hard black) | P1 | |
| 37 | Rounded corner on the note window itself (DWM rounded corners API) | P2 | Win11 only |
| 38 | Empty-state composition: a beautiful first-time hint, not a blank white box | P0 | |

## C. 窗口与贴边行为 (Window & Docking Behaviour)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 39 | Widen the edge-snap magnet zone a touch and add a faint snap preview before collapse | P1 | |
| 40 | Collapsed tab shows the note's first line as a live "peek" label (not just a handle) | P0 | high discoverability |
| 41 | Collapsed tab auto-highlights on hover (brightens, scale 1.03) before expanding | P1 | tactile |
| 42 | Drag an expanded note back off the edge to cancel auto-hide cleanly | P1 | |
| 43 | Double-click the dock tab to toggle collapse/expand | P2 | |
| 44 | Keep a note "rolled up" to only the title bar area (manual mini-mode) | P2 | |
| 45 | Snap to nearest other note edge (note-to-note magnet) | P2 | |
| 46 | Persist per-monitor position; reopening on a removed monitor restores sanely | P1 | |
| 47 | "New note opens near where I last typed" (cursor-anchored), not top-left | P1 | |
| 48 | Multi-monitor DPI: per-note position re-scaled on monitor switch (not just clamped) | P1 | ties to bug #0 |
| 49 | Avoid the dock tab overlapping the taskbar (work-area aware) | P0 | work-area bug class |
| 50 | Explicit "pin on top for this note only" quick badge that's visually obvious | P1 | |
| 51 | Smooth animated collapse/expand (200ms) instead of a hard jump | P2 | |
| 52 | Auto-hide to any edge, incl. bottom (not just top/left/right) | P2 | |

## D. 组织与自动化 (Organization & Automation)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 53 | Notes list / overview palette (Ctrl+Shift+N) — a bento grid of all notes with previews | P0 | the current UI has no overview |
| 54 | Pin/favourite a note to the front of the overview | P1 | |
| 55 | Search across all notes (live-as-you-type) with hit counts | P1 | |
| 56 | Archive (soft-delete) instead of hard delete; recover from an archive view | P1 | |
| 57 | Colour-code notes via the per-note accent; overview groups by colour | P2 | |
| 58 | Bring all notes (show/hide toggle) — split per-note and "show all" hotkeys | P1 | |
| 59 | A "today" bucket: notes touched today gated at top | P2 | |
| 60 | Duplicate a note verbatim (Ctrl+D) | P2 | |
| 61 | Export a single note to .txt/.md with one click | P1 | |
| 62 | Notes with identical first line auto-collapse into a thread | P2 | ambiguous, cull risk |
| 63 | Auto-tag via first-line #hashtag; filter tags in overview | P2 | |
| 64 | Row of quick filters in overview: All / Pinned / Today / Coloured | P2 | |
| 65 | Keyboard-first overview navigation (arrows + Enter) | P1 | |
| 66 | Batch delete in overview (multi-select) | P2 | |
| 67 | Reminder / "nag" a note after X hours (tray notification) | P2 | scope creep |
| 68 | A tiny per-note "updated HH:MM" subtitle in the overview card | P2 | |

## E. 快速捕捉与输入 (Quick Capture & Input)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 69 | Quick-capture hotkey already grabs cursor position; add a tiny "captured" toast so it feels responsive | P1 | |
| 70 | Quick-capture should not steal focus if the user is typing elsewhere (non-activating) | P0 | avoid interrupt |
| 71 | Quick-capture has a one-line "quick note" precedence: short text → tiny note | P2 | |
| 72 | Clipboard-first quick capture: global hotkey grabs current selection via clipboard | P1 | |
| 73 | Paste as plain text by default on quick capture (strip rich source) | P1 | |
| 74 | System tray quick-add input box (tray popup) | P2 | |
| 75 | Ctrl+Shift+Space toggles transparent/click-through for an active note | P1 | quick access |
| 76 | Per-note default window mode remembered on reopen | P1 | |
| 77 | Hotkey to cycle a note through 普通→置顶→嵌入桌面 | P2 | |
| 78 | Quick-capture positions new note at the mouse but clamped fully on-screen | P0 | ties to clamp bug |

## F. 可发现性、帮助与打磨 (Discoverability, Help & Polish)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 79 | A first-run "welcome" note with the hotkey cheat sheet, not just blank | P1 | empty-state |
| 80 | Context-menu items reworded to plain language (remove 【窗口模式】bracket headers) | P0 | taste: plain labels |
| 81 | Tray tooltip shows count + next reminder; tray menu is 1-level, not layered | P1 | |
| 82 | No brand-neutral "dull" default; ship with a small personality in the welcome art | P2 | anti-slop |
| 83 | Consistent iconography (one icon family) across tray, badges, toolbar | P1 | |
| 84 | Toolbar buttons get tooltips (1-line hover) | P1 | |
| 85 | Memory-trim is silent; show an occasional "memory cleaned" only in debug | P2 | |
| 86 | Add a real app menu / settings window for global prefs (currently context-menu only) | P2 | |
| 87 | Onboarding highlight for the dock-to-edge auto-hide feature | P2 | |
| 88 | A concise README/USER_GUIDE refresh matching the actual current shortcuts | P1 | docs accuracy |

## G. 性能与可靠性 (Performance & Reliability)

| # | Idea | Pri | Notes |
|---|------|-----|-------|
| 89 | Lazy-render notes that are off-screen / hidden (don't draw hidden windows) | P1 | perf |
| 90 | Debounce SaveRtfBase64 on the render thread to avoid jank while typing | P1 | |
| 91 | Do not call UpdateLayeredWindow when nothing changed (dirty-flag render) | P1 | perf |
| 92 | Crash-recovery: reopen notes after an abnormal exit (autosave journal) | P1 | |
| 93 | De-dupe concurrent instances; second launch focuses the running one | P1 | |
| 94 | Font glyph cache reuse across notes that share a family/size | P2 | |
| 95 | Release idle resources (already exists) — add a visible knob to tune the idle time | P2 | |
| 96 | Validate the single-file 5MB limit stays green (CI already does) | P1 | |
| 97 | Add a FPS/GC-style debug overlay behind a flag for perf work | P2 | |
| 98 | Persist autosave on WM_QUERYENDSESSION without blocking shutdown | P1 | |
| 99 | Do not recreate the D2D target on every resize (cache unless size actually changes) | P1 | perf |
| 100 | Log structured timing so perf regressions are bisectable | P2 | |

---

## 复盘 / Review — P0 cull

P0 list (must-do, high value, low ambiguity) after removing bad/impractical ideas:

**Kept as P0**
- 1 Paste-plain-text toggle
- 5 Character/word count footer
- 6 Auto-save "已保存 HH:MM" fade
- 17 Bold/italic/underline keyboard shortcuts
- 21 Curated contrast-safe palette system instead of raw pickers
- 24 One rounded-corner radius scale
- 31 Accent colour applied to dock tab handle
- 38 Beautiful first-run empty state
- 40 Collapsed tab shows note's first line as a peek label
- 49 Dock tab never overlaps the taskbar (work-area aware)
- 53 Notes overview / palette (bento) — fills the biggest gap
- 70 Quick-capture non-activating (don't steal focus)
- 78 Quick-capture position clamped fully on-screen
- 80 Context-menu plain labels (drop bracket headers)

**Culled / demoted (bad, ambiguous, or out of scope)**
- 62 (auto-collapse same-first-line into threads) — ambiguous, risky
- 67 (reminder/nag) — scope creep beyond a note app
- 7 (undo survives hide) — native RichEdit already mostly handles; low certifiable value
- 8, 14, 34, 37, 51 — high lift, native constraints (RTF images, spellcheck, whole-window rounding, animation) → P2
- 86 (settings window) — needs product scope, not an execution item; P2

**Executed this session (see JOURNEY/round report):** the bug-fix (drift) plus the P0 items that are
pure-code-feasible and verifiable: 5 (word count), 17 (B/I/U shortcuts), 24 (radius scale), 80 (plain
context-menu labels). The UI-heavy P0 items (1, 6, 21, 31, 38, 40, 49, 53, 70, 78) require product/visual
confirmation and are tracked as the next round.
