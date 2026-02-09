# Glitch Maker — Project Status

## v6.0 — Menu Separator, Header Colors Fixed (current)

### Menu Bar Separator
- Added `border-bottom: 1px solid border` to `QMenuBar` stylesheet in `setStyleSheet()`
- Creates a continuous horizontal line below File/View/Options/Effects/Help

### Header Colors Fixed — QPalette Approach
The previous stylesheet-based approach (`background: bg_medium` on objectName) was overridden by Qt's stylesheet cascade from parent widgets. Switched to `QPalette` which is immune to cascade:
- **EffectsPanel**: `setAutoFillBackground(True)` + `palette.setColor(Window, bg_panel)` on self, `palette.setColor(Window, bg_medium)` on header widget
- **EffectHistoryPanel**: same pattern — palette bg_panel on self, palette bg_medium on header
- **main_window.py**: removed all `background` stylesheets from `#effectsPanel` and `#effectHistoryPanel` — panels handle their own colors internally
- Header `border-bottom` still via minimal stylesheet (palette doesn't support borders)

### Documentation
- README.md: v6.0 changelog (bilingual), v5.11 collapsed
- manual_en.html / manual_fr.html: footer v6.0
- PROJECT_STATUS.md: this entry
- APP_VERSION: "6.0"

---

## v5.11 — Perfect Layout Lines, Independent Zoom

### Layout Refactor — Continuous Separator Lines
Replaced panel-level borders with explicit separator widgets in the main HBox layout:
- **Removed** `border-right` from `#effectsPanel` and `border-left` from `#effectHistoryPanel`
- **Added** two 1px-wide `QWidget` vertical separators (`vsep_left`, `vsep_right`) between the 3 columns
- These separators span the full window height, creating perfectly continuous vertical lines
- All 3 headers (Effects, Toolbar, History) use `setFixedHeight(36)`, `bg_medium`, `border-bottom: 1px`
- Headers use `setObjectName` + `setAutoFillBackground(True)` for robust color application
- `left_panel.setFixedWidth(220)` instead of `setMaximumWidth`
- `QFrame` + `QScrollBar` added to main_window.py imports

### Independent Zoom — Waveform ≠ Timeline
- `_on_waveform_zoom()`: Only updates minimap, no longer syncs to timeline
- `_on_timeline_zoom()`: Only shows/updates `_tl_scrollbar`, no longer syncs to waveform
- `_on_minimap_click()`: Only scrolls waveform, no longer syncs to timeline
- `_on_tl_scroll()`: New handler — horizontal scrollbar drives timeline offset
- `_tl_scrollbar`: 10px horizontal QScrollBar, hidden when zoom=1, styled to match theme
- Reset: `_tl_scrollbar.setVisible(False)` and timeline zoom reset on project new/load

### Minimap Threshold Lowered
- `minimap_widget.py`: visibility threshold changed from `zoom > 1.5` to `zoom > 1.05`
- Minimap appears at the slightest zoom instead of waiting for 1.5x

### Documentation
- README.md: v5.11 changelog (bilingual), v5.10 collapsed
- manual_en.html / manual_fr.html: Updated center, minimap, timeline zoom descriptions for independent zoom, footer v5.11
- PROJECT_STATUS.md: this entry
- APP_VERSION: "5.11"

---

## v5.10 — Layout Separators, Automation Removed

### Separator Lines Between Major UI Sections
Added `1px solid border` separator lines to delineate the main layout areas:
- **Effects panel → center**: `border-right: 1px solid border` on `#effectsPanel` via `setObjectName`
- **Toolbar → waveform**: `border-bottom: 1px solid border` on toolbar widget
- **Waveform → timeline**: `QFrame.HLine` separator (1px) inserted between waveform and timeline_w
- **Timeline → transport**: `QFrame.HLine` separator (1px) inserted before transport bar
- **Center → effect history**: `border-left: 2px solid border` on `#effectHistoryPanel` (unchanged from v5.8)

Added `QFrame` to `main_window.py` imports.

### Automation Removed
- **Import removed**: `from gui.automation_widget import AutomationLane, AutomationBar`
- **Widgets removed**: `auto_bar` and `auto_lane` no longer created or added to layout
- **Signals removed**: `auto_bar.toggled`, `auto_bar.param_changed`, `auto_bar.reset_clicked`
- **View menu entry removed**: `("automation", t("view.automation"), False)` from panels list
- **Method removed**: `_toggle_automation(self, enabled)`
- **Panel map cleaned**: `automation` key removed from `_toggle_panel()`
- **Translations removed**: `view.automation` key from `en.json` and `fr.json`
- 223 keys remain in parity EN/FR

### Documentation
- README.md: v5.10 changelog, automation removed from features
- manual_en.html / manual_fr.html: footer v5.10
- PROJECT_STATUS.md: this entry
- APP_VERSION: "5.10"

---

## v5.9 — Cleaner UI, 3 Settings Dialogs

### Separator Lines Removed
All white `QFrame.HLine` separators removed throughout the UI:
- **effects_panel.py**: Removed separator below search bar, between effect categories, before presets, between preset tags. Replaced with `addSpacing()` (4–10px). Removed unused `_sep()` method and `QFrame` import.
- **effect_history.py**: Removed separator lines between history items. Replaced with `spacing(3)` in layout. Removed `QFrame` import. Each item now has a rounded card background (`bg_dark`, `border-radius: 4px`) with smooth hover glow using `QPainter.drawRoundedRect`.
- **settings_dialog.py**: All `QFrame.HLine` separators removed from Audio and Language dialogs. Clean spacing-only layout.

### 3 Separate Settings Dialogs
`LanguageSettingsDialog` split into two:
- `LanguageSettingsDialog` — language selection only (360×200)
- `ThemeSettingsDialog` — theme selection only (360×200)
- `AudioSettingsDialog` — unchanged (460×300)

New menu entry: `Options > Theme` (`menu.options.theme`).
Handler `_settings_theme()` added to `main_window.py`.
Import updated: `from gui.settings_dialog import AudioSettingsDialog, LanguageSettingsDialog, ThemeSettingsDialog`.

### Translations Added
- `menu.options.theme`: EN "Theme" / FR "Thème"
- `settings.theme_title`: EN "Theme" / FR "Thème"

### Documentation
- **README.md**: v5.9 changelog (bilingual). v5.8 moved to collapsed `<details>`.
- **manual_en.html / manual_fr.html**: Settings section updated for 3 dialogs. Footer v5.9.
- **PROJECT_STATUS.md**: This entry.
- **APP_VERSION**: "5.9"

---

## v5.8 — UI Polish, Cut, Timeline Zoom, Minimap Drag

### Part 1: UI & Visual Improvements

**Effect History background harmonized** — Changed from `bg_dark` to `bg_panel` to match the effects panel. Scroll area also updated.

**Separator lines between UI blocks** — Added `QFrame` HLine separators between history items, collapsible sections in effects panel (favorites, categories, preset tags), and below the search bar. Style: 1px height, `border` color.

**Search bar background** — Changed from `bg_dark` to `bg_panel` for visual consistency.

**Split settings dialogs** — `SettingsDialog` replaced by two separate dialogs:
- `AudioSettingsDialog`: output/input device selection only
- `LanguageSettingsDialog`: language + theme selection
- Backward compatibility alias: `SettingsDialog = AudioSettingsDialog`

**Enlarged Refresh button** — Height 32px (was 22px), min-width 120px, font 12px bold. Positioned above combo boxes with 12px spacing, right-aligned.

### Part 2: Timeline Zoom, Minimap Drag, Cut

**Timeline zoom with mouse wheel** — `TimelineWidget` now has `_zoom`, `_offset`, `_max_zoom` state and `wheelEvent()`. Coordinate helpers (`_x_to_sample`, `_sample_to_x`, `_clip_at`) updated to respect zoom. Paint method renders only visible clips with adaptive time ruler. `zoom_changed` signal forwards to waveform.

**Bidirectional zoom sync** — Waveform wheel → updates timeline + minimap. Timeline wheel → updates waveform + minimap. Minimap drag → updates both.

**Draggable minimap** — `MinimapWidget` now supports click + drag (was click-only). Cursor changes to `ClosedHand` during drag. Emits `region_clicked` continuously while dragging.

**Scrollbar removed** — `QScrollBar` removed from waveform area. The minimap replaces its functionality entirely.

**Blue anchor overflow fix** — Timeline's blue anchor line now starts at `y0=14` (clip area) instead of `y=0`, matching the green playhead behavior.

**Cut selection on waveform** — Right-click inside a red selection shows two options:
- "Cut — Replace with silence": splits affected clips into 3 parts (before, silence, after)
- "Cut — Remove & splice": splits into 2 parts (before, after), audio becomes shorter
- New signals: `cut_silence_requested(int, int)`, `cut_splice_requested(int, int)`
- Translation keys added: `cut.replace_silence`, `cut.splice`

**Distinct colors on split/cut** — Uses `_generate_distinct_color()` from `core/timeline.py` (golden-angle hue rotation) for all new clips created by split, cut-silence, and cut-splice.

### Part 3: Documentation

**README.md** — Fully bilingual (EN/FR). Updated to v5.8 with complete changelog covering all 3 parts. Previous versions collapsed in `<details>` tags.

**manual_en.html / manual_fr.html** — Updated sections: Interface (minimap mention), Timeline (zoom, cut feature), Settings (split dialogs), Shortcuts (mouse wheel zoom). Version footer updated.

**PROJECT_STATUS.md** — This file. Full technical breakdown of all changes.

**APP_VERSION** — Updated to "5.8" in `utils/config.py`.

---

## v5.6 — Anchor Playback, Grid Fix, UI Polish

### Grid Display Fixed
`_set_grid()` only set `grid_subdivisions` and `bpm` properties but never called `set_grid(enabled=True, ...)`. The grid was never enabled. Now calls `waveform.set_grid(subdiv > 0, bpm, 4, subdiv)`.

### Anchor-Based Playback
- **Play**: starts from blue anchor if no selection (was: always from 0)
- **Stop**: returns to blue anchor position (was: returns to selection start or 0)
- **Seek**: clicking waveform sets both playhead AND anchor, syncs to timeline
- **Timeline seek**: dragging timeline anchor syncs to waveform anchor

### Minimap Scroll Sync
`_on_wave_scroll()` now also calls `minimap.set_view(zoom, offset)` so the overview follows scrollbar changes, not just mouse wheel zoom.

### Last Clip Deletion Prevention
`_del_clip()` checks `len(self.timeline.clips) <= 1` and shows message instead of deleting.

### New Project Full Reset
Clears: audio_data, waveform (audio, anchor, playhead, selection, zoom cache), minimap (audio, cache, hidden), timeline (anchor, playhead), transport (time, selection, playing state), undo/redo stacks.

### UI Fixes
- Effect history: `#effectHistoryPanel` objectName selector for border (was: cascading to children causing random bars)
- Effects panel scrollbar: 8px width, bg matches panel, hover effect on handle
- Timeline: green playhead starts at y=14 (below time ruler), green triangle added to distinguish from blue anchor

---

## v5.5 — UI Cleanup & Minimap Fix

### Effect Chain Removed
- `EffectChainWidget` removed from left panel layout, signal connections, view menu, panel toggle map
- Import `from gui.effect_chain import EffectChainWidget` removed
- Effects are now managed exclusively via the Effect History panel (right)

### Effect History Panel
- Now **visible by default** (view menu checked=True)
- **No auto-open**: previously, `_sync_history_chain()` would force-show the panel whenever effects were added. Removed this behavior — if user closes it, it stays closed until manually reopened.
- Added `border-left: 2px solid` for clear visual separation from waveform area

### Minimap Crash Fixed
- `self.minimap.set_visible_region(...)` → `self.minimap.set_view(zoom, offset)` — the method is `set_view`, not `set_visible_region`

### Documentation
- EN/FR manuals updated: all "effect chain" / "chaîne d'effets" references removed
- Reorder (▲ ▼) instructions removed from "Managing effects" section

---

## v5.4 — Effects Crash Fix & Latency Reduction

### Critical Crash Fixed: All Effects
**Root cause**: `load_plugins()` returns a **dict** `{id: Plugin}`. But `_find_plugin()` did `for p in self._plugins: if p.id == ...` — iterating a dict iterates over **keys** (strings), not values. So `p` was `"reverse"` (a str) and `p.id` → `AttributeError: 'str' object has no attribute 'id'`.

**Fix**: Direct dict lookup `self._plugins[effect_id]` + fallback `self._plugins.values()` for name-matching.

### Audio Latency Reduction
- Stream is now created BEFORE `is_playing = True` in all play methods (play, resume, play_selection)
- Previously: `is_playing = True` then stream created → callback missed first frames → audible delay
- Timer reduced from 33ms (30fps) to 16ms (60fps) for tighter audio-visual synchronization
- Progressive stream configuration: tries `blocksize=256,latency='low'` first, falls back through 5 configs

### Other Fixes
- `set_plugins()` → `reload_plugins()` on plugin import (method that actually exists)

---

## v5.3 — Click+Play Crash Fix & Crash Logging

### Critical Crash Fixed
**Root cause**: `_seek()` was called when clicking on the waveform. Two bugs:
1. `transport.set_time(t_str)` — called with 1 argument, but `set_time(self, c, t)` requires 2 → `TypeError` → instant crash on any waveform click
2. `sample = int(pos * total)` — `pos` is a sample index (e.g. 44100) emitted by `position_clicked(int)`, NOT a 0-1 fraction. Multiplying by total gave astronomical values, clamped to end-of-file → clicking anywhere always sought to the end

Same issue in `_on_sel(s, e)` — `s * total` and `e * total` were wrong; s and e are sample indices from `selection_changed(int, int)`.

### Crash Logging System
- `logs/` directory created next to the executable (or script)
- `logs/crash.log` — appended with full traceback, timestamp, Python version, platform
- `logs/glitchmaker.log` — rotating log file (2MB max, 3 backups), all DEBUG+ messages
- `sys.excepthook` in `main.py` catches all unhandled exceptions:
  - Writes crash report to file
  - Shows `QMessageBox.critical` with error details and log path
  - Prints traceback to stderr

### Robustness
All playback-related methods wrapped in try/except with logging:
- `_toggle_play()`, `_play()`, `_stop()`, `_seek()`, `_seek_from_timeline()`, `_on_sel()`

---

## v5.2 — Playback Stability & UX

### Playback Crash Fix (Critical)
- **Root cause**: `on_playback_finished` callback was called from the sounddevice audio thread (C-level real-time thread). It called `self.transport.set_playing(False)` which modified a Qt widget from a non-GUI thread → segfault.
- **Fix**: Added `_sig_playback_done = pyqtSignal()` to MainWindow. The callback now emits the signal, which is received on the GUI thread. All Qt widget modifications happen safely.
- Audio callback (`_callback`) now wrapped in try/except — any error silences output instead of crashing.

### Auto-Default Audio Device
- `PlaybackEngine.output_device = None` by default → uses system default device
- `_ensure_stream()` now has fallback: if configured device fails, automatically retries with `device=None` (system default)
- Stream uses `blocksize=512, latency='high'` for maximum hardware compatibility
- New `refresh_device()` method: re-creates the stream while preserving playback state

### Device Hot-Plug
- Settings dialog now has a **Refresh ↻** button that re-scans audio devices via `sd.query_devices()`
- Users can detect newly plugged headphones/interfaces without restarting the app
- Translation key `settings.refresh` added (EN/FR)

### Settings Dialog Cleanup
- Removed `QFrame` separator lines between sections
- Added 16px spacing between sections (was 12px + separator + 12px)
- Added 24px spacing between theme combo and action buttons (was `addStretch` only)

### Comprehensive Manuals
- EN and FR manuals completely rewritten (287/286 lines each)
- All 22 effects documented with: description, parameter explanation, audio example
- All 20 presets described with expected sound
- Sections: Files, Interface, Playback, Effects, Presets, Timeline, Undo, Metronome, Markers, Settings, Shortcuts
- No technical/development sections — pure user manual

### Other
- `_play()` wrapped in try/except
- `_upd_playhead()` correctly resets transport button when playback ends naturally

---

## v5.1 — Playback & API Fix

### Missing PlaybackEngine Methods
Six methods/properties referenced by main_window but never implemented in PlaybackEngine:
- `current_position` — property alias for `position`, used by timer 30×/sec
- `resume()` — resume after pause (set is_playing=True, ensure stream)
- `play_selection(start, end)` — play a selected range with loop
- `toggle_metronome(bpm)` — toggle metronome on/off
- `bpm` / `metronome_on` / `metronome_vol` — property delegates to Metronome

### Missing Waveform Properties
- `clear_selection()` — clear selection without resetting everything
- `bpm` property → `_grid_bpm` (used when setting BPM from toolbar)
- `grid_subdivisions` property → `_grid_subdiv` (used by beat grid)

### Other Fixes
- `spectrum.update_from_audio()` → `update_spectrum(chunk, sr)` (correct API)
- `_upd_playhead()` timer callback wrapped in try/except (no more timer crashes)
- `play()` now clears looping state (no stuck loops from previous selections)
- Playback finished detection: transport button resets when playback ends naturally

---

## v5.0 — Stability & Reliability

### Undo/Redo System Rework
- `_base_audio` is now saved and restored in every undo/redo snapshot
- Removed redundant `audio_backup` from snapshots — audio is re-rendered from base + ops on restore
- Memory usage reduced ~3× (20 levels × base + clips only, no rendered audio copies)
- Undo after .gspi reload works correctly (re-renders instead of restoring missing audio)

### Crash Protection
- Timeline `paintEvent` and `mousePressEvent` wrapped in try/except/finally
- Waveform `paintEvent` wrapped in try/except/finally
- `set_selection()` handles None values safely
- Preview `_start_preview()` wrapped in try/except
- `playback.resume_stream()` wrapped in try/except

### Clip Operations Fixed
- Split, duplicate, delete, reorder all clear `_effect_ops` and reset `_base_audio`
- Fades (in/out) update `_base_audio` and re-render existing ops on top
- No more stale ops referencing old audio positions after clip structure changes

### Non-Destructive Render Engine
- `_render_from_ops()`: global effects (`is_global=True`) now use `len(self.audio_data)` dynamically
- Non-global effects properly clamped to current audio length after length-changing ops

### Other Fixes
- Marker system: fixed `add_marker()` call signature, `get_markers()` API used correctly
- 4 missing translation keys added: `confirm.unsaved`, `metro.enable`, `metro.volume`, `stems.single`
- `project.py` save version updated to 5.0
- All 218 translation keys EN/FR in parity

---

## v4.5 — Bug Fixes & Cleanup

- Fixed: Delete key crash (no handler existed)
- Fixed: Effect click crash (no error handling in `_on_effect`)
- Fixed: Clip deletion crash (edge cases)
- Added: File > New (Ctrl+N) with unsaved changes prompt
- Added: Unsaved prompt when loading .gspi files
- Removed: Multi-select / chain apply system from effects panel
- Added: Bug report links (GitHub: Spiralyfox) in About dialog and docs
- Updated: Translations EN/FR (214 keys), documentation, manuals

## v4.4 — Non-Destructive Architecture

- Non-destructive effect system: base_audio + effect_ops → rendered audio
- Effect history right sidebar with timestamps, toggle, delete
- Effect chain left sidebar with reorder (▲▼), toggle, delete
- Clip colors on timeline
- Project save/load (.gspi) with full undo/redo state
- Removed: Glitch Sequencer and XY Pad (stability)

## v4.0–4.3 — Advanced Features

- v4.0: Glitch Sequencer (step sequencer for effects), Effect Chain Rack
- v4.1: XY Pad with real-time 2D parameter control
- v4.2: Preset manager improvements, effect chain polish
- v4.3: Settings fixes, history timestamps, preset cleanup

## v3.0 — Timeline & Multitrack

- Multi-clip timeline with drag & drop reorder
- Split, duplicate, delete, fade in/out operations
- FFmpeg auto-download system
- Metronome with beat grid overlay
- Export stems (individual clips)

## v2.0 — Foundation

- 37 audio effects with plugin architecture
- Bilingual interface (FR/EN) with 200+ translation keys
- Dark/Light themes
- Waveform with zoom, selection, markers
- Preset system (20 voice presets)
- Recording dialog with device selection
- 54 unit tests

---

**Tech stack:** Python 3.10+, PyQt6, numpy, soundfile, scipy, sounddevice  
**Author:** Théo (Spiralyfox) — https://github.com/Spiralyfox
