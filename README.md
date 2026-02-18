# Glitch Maker 🎵

## 🇫🇷 Français

**Glitch Maker** est une station de travail d'effets audio créatifs conçue pour le sound design, le glitch art sonore et l'expérimentation musicale. Chargez n'importe quel fichier audio (MP3, WAV, FLAC, OGG…) et appliquez des effets destructifs, modulaires ou texturants en temps réel sur tout ou partie du signal.

### Ce que fait Glitch Maker

Glitch Maker permet de transformer radicalement un fichier audio en lui appliquant des chaînes d'effets non-destructifs. Chaque action est enregistrée dans un historique complet : effets, coupes, fondus, ajouts de clips, enregistrements, duplications et réorganisations. Vous pouvez activer, désactiver ou supprimer chaque action indépendamment à tout moment — l'audio est recalculé depuis l'état initial. Le logiciel découpe visuellement votre audio en clips sur une timeline, et vous sélectionnez précisément la zone à traiter grâce à la sélection rouge sur la waveform.

### Fonctionnalités principales

**Interface complète** — Waveform interactive avec zoom indépendant, timeline multi-clips, minimap de navigation, analyseur de spectre en temps réel, métronome synchronisé avec grille de tempo, et transport complet (Play/Pause/Stop avec boucle automatique).

**26 effets audio** organisés en 6 catégories :
- **Basics** — Reverse, Volume, Filter, Pan/Stéréo : les outils fondamentaux.
- **Pitch & Time** — Pitch Shift, Time Stretch, Tape Stop, Pitch Drift : hauteur et vitesse.
- **Distortion** — Saturation (3 modes : Soft, Hard, Overdrive + Tone), Distortion, Bitcrusher : écrasement et dégradation volontaire.
- **Modulation** — Chorus, Phaser (feedback + stereo spread), Tremolo, Ring Mod : mouvement et profondeur.
- **Space & Texture** — Delay (queue mixée sur la suite audio), Vinyl, OTT, Robotic : espace, texture et ambiances.
- **Glitch** — Stutter, Granular, Shuffle, Buffer Freeze, Datamosh, Tape Glitch, Digital Noise : effets destructifs et expérimentaux.

**Historique complet** — Toutes les actions sont tracées dans le panneau Historique avec icônes et couleurs par type (effets, automations, coupes, fondus, ajouts, enregistrements, suppressions, duplications, réorganisations). Toutes les actions sont activables/désactivables et supprimables individuellement — l'audio est entièrement recalculé depuis l'état initial en rejouant les actions activées dans l'ordre. Le mapping de coordonnées (v7) garantit que les coupes et effets s'appliquent toujours à la bonne zone audio, même quand des opérations antérieures sont désactivées. Annuler/refaire avec Ctrl+Z / Ctrl+Y.

**Automations** — Automatisez un ou plusieurs paramètres d'effet au fil du temps, comme dans FL Studio. Sélectionnez une zone, choisissez un effet, cochez les paramètres à automatiser (avec courbe éditable From → To) ou à fixer en valeur constante. L'éditeur de courbe propose deux modes : **Points** (ajouter, déplacer, supprimer des points de contrôle) et **Bend** (courber les segments en Bézier quadratique). Aperçu waveform en temps réel (grise = original, violette = traité). Prévisualisation audio avec barre de lecture.

**Sélection intelligente** — Pendant la lecture, glisser pour sélectionner met automatiquement en pause. En relâchant, la lecture reprend dans la zone sélectionnée.

**Timeline multi-clips** — Assemblez plusieurs fichiers audio. Supprimez (avec confirmation), divisez, dupliquez et réorganisez les clips par glisser-déposer. Appliquez des fondus (Fade In / Fade Out) avec une enveloppe Bézier dessinée directement sur la waveform — modes Points et Bend, prévisualisation audio, mémorisation des paramètres.

**Édition** — Coupez des portions d'audio (remplacement par silence ou suppression avec recollage) avec confirmation avant chaque opération. Placez des marqueurs n'importe où sur la waveform via clic droit et naviguez entre eux.

**Enregistrement** — Enregistrez depuis votre micro avec une interface dédiée : vumètre animé multibarres avec gradient de couleur, chronomètre précis au dixième de seconde, indicateur d'état clignotant. L'audio est automatiquement rééchantillonné pour correspondre au taux du projet, évitant tout problème de hauteur.

**Presets & Plugins** — Créez des presets avec chaînes d'effets configurables. Testez-les en direct (Play original / Play with preset). Gérez via « My Presets » (triés par tags, modifiables) et « Built-in » (lecture seule). Import/export au format .pspi. Importez des plugins d'effets personnalisés (.py).

**Multi-langue** — Français et anglais. Interface mise à jour instantanément.

**Personnalisation** — Thème sombre/clair, réglages audio (entrée/sortie), métronome configurable (BPM, volume).

### Installation & Lancement

**Option 1 — Lancer avec Python :**

```bash
pip install -r requirements.txt
python main.py
```

**Option 2 — Compiler en .exe (Windows) :**

Double-cliquez sur `build.bat` — le script installe les dépendances, compile avec PyInstaller, et génère `dist\GlitchMaker.exe`.

**Données utilisateur :** Paramètres, presets, tags et logs sont stockés dans un dossier `data\` créé automatiquement. Supprimez-le pour un reset complet.

FFmpeg est téléchargé automatiquement au premier lancement si nécessaire.

### Raccourcis clavier

| Raccourci | Action |
|---|---|
| Espace | Lecture / Pause |
| Escape | Désélectionner |
| Ctrl+Z | Annuler |
| Ctrl+Y | Refaire |
| M | Ajouter un marqueur |
| Ctrl+← / Ctrl+→ | Marqueur précédent / suivant |
| Suppr | Supprimer le clip sélectionné |
| Molette (waveform) | Zoom waveform |
| Molette (timeline) | Zoom timeline |

---

## 🇬🇧 English

**Glitch Maker** is a creative audio effects workstation designed for sound design, audio glitch art and musical experimentation. Load any audio file (MP3, WAV, FLAC, OGG…) and apply destructive, modular or texturing effects in real time on all or part of the signal.

### What Glitch Maker does

Glitch Maker lets you radically transform an audio file by applying non-destructive effect chains. Every action is recorded in a full history: effects, cuts, fades, clip additions, recordings, duplications and reorders. You can enable, disable or delete any action independently at any time — audio is recalculated from the initial state. The software visually slices your audio into clips on a timeline, and you precisely select the area to process using the red selection on the waveform.

### Key features

**Complete interface** — Interactive waveform with independent zoom, multi-clip timeline, navigation minimap, real-time spectrum analyser, metronome synchronised with beat grid, and full transport (Play/Pause/Stop with automatic looping).

**26 audio effects** organised in 6 categories:
- **Basics** — Reverse, Volume, Filter, Pan/Stereo: fundamental tools.
- **Pitch & Time** — Pitch Shift, Time Stretch, Tape Stop, Pitch Drift: pitch and speed.
- **Distortion** — Saturation (3 modes: Soft, Hard, Overdrive + Tone), Distortion, Bitcrusher: crushing and deliberate degradation.
- **Modulation** — Chorus, Phaser (feedback + stereo spread), Tremolo, Ring Mod: movement and depth.
- **Space & Texture** — Delay (echo tail blends with following audio), Vinyl, OTT, Robotic: space, texture and atmospheres.
- **Glitch** — Stutter, Granular, Shuffle, Buffer Freeze, Datamosh, Tape Glitch, Digital Noise: destructive and experimental effects.

**Full history** — All actions are tracked in the History panel with icons and colours by type (effects, automations, cuts, fades, additions, recordings, deletions, duplications, reorders). All actions can be toggled on/off and deleted individually — audio is fully recalculated from the initial state by replaying enabled actions in order. Coordinate mapping (v7) ensures cuts and effects always apply to the correct audio region, even when earlier operations are disabled. Undo/redo with Ctrl+Z / Ctrl+Y.

**Automations** — Automate one or more effect parameters over time, like in FL Studio. Select a region, choose an effect, check parameters to automate (with editable From → To curve) or set as constant. The curve editor offers two modes: **Points** (add, move, delete control points) and **Bend** (curve segments with quadratic Bézier). Real-time waveform preview (grey = original, purple = processed). Audio preview with playback bar.

**Smart selection** — While playing, dragging to select automatically pauses. On release, playback resumes inside the selected region.

**Multi-clip timeline** — Combine multiple audio files. Delete (with confirmation), split, duplicate and reorder clips via drag-and-drop. Apply fades (Fade In / Fade Out) with a Bézier envelope drawn directly on the waveform — Points and Bend modes, audio preview, parameter memory.

**Editing** — Cut audio portions (replace with silence or splice) with a confirmation dialog before each operation. Place markers anywhere on the waveform via right-click and navigate between them.

**Recording** — Record from your microphone with a dedicated interface: animated multi-bar level meter with colour gradient, precise timer showing tenths of seconds, blinking status indicator. Audio is automatically resampled to match the project's sample rate, preventing pitch issues.

**Presets & Plugins** — Create presets with configurable effect chains. Test live (Play original / Play with preset). Manage via "My Presets" (sorted by tags, editable) and "Built-in" (read-only). Import/export as .pspi files. Import custom effect plugins (.py).

**Multi-language** — French and English. Instant interface update.

**Customisation** — Dark/light theme, audio settings (input/output), configurable metronome (BPM, volume).

### Installation & Launch

**Option 1 — Run with Python:**

```bash
pip install -r requirements.txt
python main.py
```

**Option 2 — Compile to .exe (Windows):**

Double-click `build.bat` — the script installs dependencies, compiles with PyInstaller, and generates `dist\GlitchMaker.exe`.

**User data:** Settings, presets, tags and logs are stored in a `data\` folder created automatically. Delete it for a full reset.

FFmpeg is automatically downloaded on first launch if needed.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Space | Play / Pause |
| Escape | Deselect |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| M | Add marker |
| Ctrl+← / Ctrl+→ | Previous / next marker |
| Delete | Delete selected clip |
| Scroll wheel (waveform) | Waveform zoom |
| Scroll wheel (timeline) | Timeline zoom |

---

## Crédits / Credits

**Auteur / Author** : Mattéo Dauriac (alias : Spiralyfox)

**Projet / Project** : [github.com/Spiralyfox/GlitchMaker](https://github.com/Spiralyfox/GlitchMaker)

**GitHub** : [github.com/Spiralyfox](https://github.com/Spiralyfox)

Built with Python, PyQt6, NumPy, SciPy, sounddevice, soundfile.
