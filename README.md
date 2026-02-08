# Glitch Maker v3.10

Application desktop d'edition et de glitching audio pour la production **digicore / hyperpop / glitchcore / dariacore**.

Interface sombre style DAW avec waveform interactive, timeline multi-clips, 28 effets audio, 25 presets, metronome et grille de temps.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Installation

```bash
pip install -r requirements.txt
python main.py
```

Pour les formats MP3/M4A, installer FFmpeg :
```bash
winget install ffmpeg
```

## Compilation .exe

```bash
build.bat
```

Resultat dans `dist/Glitch.exe` (standalone, pas besoin de Python installe).

## Fonctionnalites

### 28 Effets audio (6 categories)

| Categorie | Effets |
|-----------|--------|
| **Basics** | Reverse, Volume, Filter (LP/HP/BP + sweep), Pan |
| **Pitch & Time** | Pitch Shift, Time Stretch, Tape Stop, Autotune (chromatique + gammes), Wave Ondulee |
| **Distortion** | Saturation (3 types), Distortion (fuzz/overdrive), Bitcrusher (bit depth + downsample) |
| **Modulation** | Chorus, Phaser, Tremolo, Ring Modulator |
| **Space & Texture** | Delay Feedback, Vinyl Crackle, OTT Compression, Voix Robotique, Hyper (one-knob hyperpop) |
| **Glitch** | Stutter, Granular, Slice Shuffle, Buffer Freeze, Datamosh, Vocal Chop, Tape Glitch |

Chaque effet a une fenetre de parametres avec preview audio en temps reel.
Les icones des effets affichent la lettre initiale sur un carre colore.

### 25 Presets

Presets classes par tags avec pastille couleur :

- **Autotune** : Hard Autotune, Soft Autotune, Autotune + Reverb Wash
- **Hyperpop** : 100 gecs Mode, Hyperpop Maximum, Hyperpop Lite, Digital Angel, Nightcore Classic
- **Digicore / Dariacore** : Digicore Vocal Edit, Dariacore Chop, Dariacore Smash
- **Lo-fi / Tape** : Vinyl Nostalgia, Lo-fi Tape Mess, Tube Warmth
- **Ambient / Psychedelic** : Underwater, Dreamy Slowdown, Psycho Phaser, Wave Dream
- **Glitch / Experimental** : Electro Stutter, Sidechain Pulse, Fuzz Demon, Emocore Vocal
- **Vocal** : Robot Voice, Thick Chorus, Nightcore

Export / import de presets au format `.pspi`.

### Metronome & Grille de temps

- **Metronome** : clic de tempo synchronise a la lecture (BPM 20-300, volume, signature rythmique)
- **Grille** : overlay sur la waveform avec lignes de mesures, temps et subdivisions
- Choix de resolution : Bar, Beat, 1/2, 1/3, 1/4, 1/6, 1/8, 1/12, 1/16
- Controles BPM avec boutons +/- (auto-repeat) dans la toolbar

### Waveform interactive

- Zoom a la molette (centre sur curseur, jusqu'a x100)
- Barre de scroll horizontale quand zoome (entre waveform et timeline)
- Selection par drag avec curseur bleu
- Playhead temps reel
- Grille de temps superposee
- Indicateur de zoom (x2.5, x10, etc.)

### Timeline avancee

- Clips audio avec drag & drop
- Clic droit : Couper, Dupliquer, Fade In/Out, Supprimer
- Effets appliques en 3 blocs (avant / effet / apres)
- Effets globaux non-destructifs sur toute la timeline

### Projet .gspi

Format de sauvegarde complet (ZIP avec clips WAV + metadata JSON).
Sauver / ouvrir via le menu Fichier ou drag & drop.

### Multi-langue

Interface disponible en francais et anglais (extensible).
Changement de langue instantane dans Options > Langue.

### Import de plugins

Possibilite d'importer des effets personnalises (fichiers `.py` avec classe `Plugin`).

## Raccourcis clavier

| Touche | Action |
|--------|--------|
| Espace | Play / Pause |
| Ctrl+Z | Annuler (30 niveaux) |
| Ctrl+Y | Retablir |
| Ctrl+O | Importer audio |
| Ctrl+S | Export WAV |
| Ctrl+Shift+S | Sauver projet |
| Ctrl+A | Tout selectionner |
| Escape | Deselectionner |
| Double-clic | Tout selectionner |
| Molette | Zoom waveform |

## Formats supportes

| Type | Formats |
|------|---------|
| Import | WAV, MP3, FLAC, OGG, M4A, AIFF |
| Export | WAV, MP3, FLAC |

## Architecture du code

```
main.py                     Point d'entree
utils/
  config.py                 Couleurs, chemins, settings
  translator.py             Systeme i18n (t() pour traduire)
core/
  audio_engine.py           Chargement / export audio (WAV, MP3, FLAC)
  playback.py               Lecture temps reel (sounddevice, low-latency)
  metronome.py              Generation de clics synchronises au BPM
  timeline.py               Modele de donnees timeline (clips)
  project.py                Sauvegarde / chargement projet .gspi
  preset_manager.py         Gestion des presets (builtin + user)
  effects/                  28 effets audio (un fichier par effet)
gui/
  main_window.py            Fenetre principale (toolbar, menus, connexions)
  waveform_widget.py        Affichage waveform (zoom, grille, selection)
  timeline_widget.py        Affichage timeline (clips, drag, context menu)
  transport_bar.py          Barre de transport (play/stop/volume)
  effects_panel.py          Sidebar effets + presets
  effect_dialogs.py         Dialogues de parametres pour chaque effet
  dialogs.py                Dialogues generaux (enregistrement, about)
plugins/
  loader.py                 Chargement des 28 plugins builtin
  user_loader.py            Import / gestion des plugins utilisateur
lang/
  en.json / fr.json         Traductions
assets/
  presets.json              Presets builtin
```

Toutes les fonctions sont documentees avec des docstrings en francais.

## Stack technique

- **GUI** : PyQt6 (theme sombre custom)
- **Audio** : numpy, scipy, sounddevice, soundfile, librosa
- **Playback** : Stream low-latency (blocksize 256, ~6ms)
- **Build** : PyInstaller (standalone .exe)
