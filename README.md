# Glitch Maker v6.0 🎵

Audio glitch art tool — Creative audio effects workstation.
*Outil de glitch audio — Station d'effets audio créatifs.*

## Features / Fonctionnalités

- **22 effects / effets** : Bitcrusher, Chorus, Delay, Reverb, Distortion, Pitch Shift, Time Stretch, Vinyl, OTT, Stutter, Granular, Filter, Phaser, Ring Mod, Saturation, Shuffle, Tape Stop, Datamosh, Buffer Freeze, Tremolo, Pan, Volume
- **Non-destructive / Non-destructif** : every effect is a reversible operation / chaque effet est une opération réversible
- **20 vocal presets / presets vocaux** : Hard Autotune, Hyperpop, Robot, Nightcore, Lo-fi, Demon Voice, Vaporwave, Glitchcore...
- **Timeline** : drag & drop, split, duplicate, fade in/out, **cut (silence or splice)**
- **Bilingual / Bilingue** : Français / English
- **Themes / Thèmes** : Dark / Light
- **Formats** : WAV, MP3, FLAC, OGG (import/export). Project .gspi with undo/redo
- **Metronome / Métronome** & **beat grid / grille de tempo**
- **Spectrum / Spectre**, **minimap**, **markers / marqueurs**
- **Zoom synced / synchronisé** : waveform ↔ timeline ↔ minimap

## What's new in v6.0 / Nouveautés v6.0

### 📐 Menu bar separator / Séparateur barre de menu
- **Fine line below menu bar** / **Ligne fine sous la barre de menu** : 1px border-bottom on QMenuBar separates File/View/Options from the rest of the UI / ligne de séparation entre le menu et le reste de l'interface

### 🎨 Header colors fixed / Couleurs d'en-tête corrigées
- **Effects and History headers now identical** / **En-têtes Effets et Historique désormais identiques** : both use QPalette to force bg_medium background — no more stylesheet cascade issues / les deux utilisent QPalette pour forcer le fond, plus de problème de couleur

## Previous versions / Versions précédentes

<details><summary>v5.11 — Perfect Layout Lines, Independent Zoom</summary>

- Continuous vertical separator lines. All headers 36px aligned. Independent waveform/timeline zoom. Timeline scrollbar. Minimap appears at slightest zoom.
</details>

<details><summary>v5.10 — Layout Separators, Automation Removed</summary>

- Separator lines between major UI sections. Automation panel and menu fully removed.
</details>

<details><summary>v5.9 — Cleaner UI, 3 Settings Dialogs</summary>

- Separator lines redesigned. Effect history cards. 3 separate settings: Audio, Language, Theme.
</details>

<details><summary>v5.8 — UI Polish, Cut, Timeline Zoom</summary>

- History panel harmonized. Separator lines added (then removed in v5.9). Search bar restyled. Split settings dialogs. Enlarged Refresh button. Cut selection (silence/splice). Distinct clip colors. Timeline zoom with mouse wheel. Draggable minimap. Scrollbar removed. Blue anchor fixed.
</details>

<details><summary>v5.6 — Anchor Playback, Grid Fix</summary>

- Grid display fixed. Stop returns to blue anchor. Play from anchor. Minimap scroll sync. Last clip deletion blocked. New Project reset. UI polish.
</details>

<details><summary>v5.5 — UI Cleanup & Minimap Fix</summary>

- Effect Chain panel removed. History visible by default. Minimap crash fixed.
</details>

<details><summary>v5.4 — Effects Crash Fix & Latency</summary>

- `_plugins` dict fix. Stream before play. Timer 60fps. Progressive fallback.
</details>

<details><summary>v5.3 — Click Crash & Logs</summary>

- `_seek()` and `_on_sel()` fixed. Crash logging. try/except everywhere.
</details>

<details><summary>v5.2 — Playback Stability</summary>

- Thread-safe signals. Auto audio output. Hot-plug. Protected callback. Manuals rewritten.
</details>

## Installation

```bash
pip install -r requirements.txt
python main.py
```

### Dependencies / Dépendances
- Python 3.10+
- PyQt6
- numpy, soundfile, scipy, sounddevice
- FFmpeg (auto-downloaded if missing / téléchargé automatiquement si absent)

## Usage / Utilisation

1. **File > Open** (Ctrl+O) to load audio / **Fichier > Ouvrir** pour charger un audio
2. Select a region on the waveform (or nothing for global) / Sélectionner une zone (ou rien pour global)
3. Click an effect in the left panel / Cliquer un effet dans le panneau gauche
4. Adjust parameters, Preview, then Apply / Ajuster les paramètres, Prévisualiser, puis Appliquer
5. The effect appears in the history panel (right) / L'effet apparaît dans l'historique (droite)
6. **Toggle** (●) or **Delete** (✕) any effect / **Activer/désactiver** (●) ou **Supprimer** (✕) chaque effet
7. **Right-click a red selection** to cut / **Clic droit sur une sélection rouge** pour couper
8. **File > Save** (Ctrl+S) saves as .gspi / **Fichier > Enregistrer** sauvegarde en .gspi

## Keyboard shortcuts / Raccourcis clavier

| Key / Touche | Action |
|---|---|
| Ctrl+N | New project / Nouveau projet |
| Ctrl+O | Open file / Ouvrir un fichier |
| Ctrl+S | Save project / Sauvegarder |
| Ctrl+Z | Undo / Annuler |
| Ctrl+Y | Redo / Refaire |
| Space / Espace | Play / Stop |
| Delete / Suppr | Delete selected clip / Supprimer le clip |
| M | Add marker / Ajouter un marqueur |
| Ctrl+← / → | Navigate markers / Naviguer entre marqueurs |
| Ctrl+A | Select all / Tout sélectionner |
| Esc / Échap | Deselect / Désélectionner |
| Mouse wheel / Molette | Zoom waveform or timeline (independent / indépendant) |

## Structure

```
main.py              Entry point / Point d'entrée
gui/                 PyQt6 interface
core/                Audio engine, timeline, project
effects/             Effect plugins
plugins/             Plugin loader
lang/                Translations EN/FR
assets/              Presets, manuals / manuels
utils/               Config, translation, logging
tests/               Unit tests
```

## Bugs & Contributions

Report bugs by creating an **issue** on GitHub:
*Signalez les bugs en créant une **issue** sur GitHub :*
👉 **https://github.com/Spiralyfox**

## Licence

Personal project — Théo (Spiralyfox)
*Projet personnel — Théo (Spiralyfox)*
