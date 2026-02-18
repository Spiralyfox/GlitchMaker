from utils.logger import get_logger
_log = get_logger("loader")
"""
Plugin loader — all effect plugins with metadata, dialogs, and process wrappers.
Each wrapper handles param name mapping between dialog output and effect function.
Called as: wrapper(audio_data, start, end, sr=sr, **dialog_params)
"""

import os
from utils.translator import t


class Plugin:
    __slots__ = ("id", "icon", "color", "section", "dialog_class", "process_fn",
                 "_name_key", "_preview_file")

    def __init__(self, eid, icon, color, section, name_key, dialog_class, process_fn,
                 preview_file=None):
        self.id = eid
        self.icon = icon
        self.color = color
        self.section = section
        self._name_key = name_key
        self.dialog_class = dialog_class
        self.process_fn = process_fn
        self._preview_file = preview_file

    def get_name(self, lang=None):
        # User plugins use special prefix
        """Retourne le nom traduit du plugin."""
        if self._name_key.startswith("_user_."):
            pid = self._name_key[7:]
            from plugins.user_loader import get_user_translation
            from utils.translator import get_language
            lang = lang or get_language()
            name = get_user_translation(pid, "name", lang)
            if name:
                return name
            # Fallback: try METADATA name from registry
            from plugins.user_loader import list_installed
            for e in list_installed():
                if e.get("id") == pid:
                    return e.get("name", pid)
            return pid
        return t(f"cat.{self._name_key}.name")

    def get_short(self, lang=None):
        """Get short description."""
        if self._name_key.startswith("_user_."):
            pid = self._name_key[7:]
            from plugins.user_loader import get_user_translation
            from utils.translator import get_language
            lang = lang or get_language()
            short = get_user_translation(pid, "short", lang)
            return short or "User effect"
        return t(f"cat.{self._name_key}.short")

    def get_preview_path(self):
        """Retourne le chemin du fichier de preview pour un plugin."""
        if not self._preview_file:
            return None
        base = os.path.dirname(os.path.abspath(__file__))
        fp = os.path.join(base, "previews", self._preview_file)
        if os.path.isfile(fp) and os.path.getsize(fp) > 100:
            return fp
        return None


# ═══ Wrappers (all accept sr= and **kw to absorb extra params) ═══

def _w_reverse(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Reverse."""
    from core.effects.reverse import reverse
    return reverse(audio_data, start, end)

def _w_volume(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Volume."""
    from core.effects.volume import volume
    return volume(audio_data, start, end, gain_pct=kw.get("gain_pct", 100))

def _w_filter(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Filter."""
    from core.effects.filter import resonant_filter

    state = kw.get("plugin_state")
    if state is not None:
        # Stateful mode: pass zi (may be None on first call)
        zi = state.get("filter_zi")
        # Pass zi="init" to signal we want stateful returns even on first call
        # resonant_filter checks `zi is not None` to decide return type
        # So pass an empty list/zeros if we have no stored state yet
        result = resonant_filter(audio_data, start, end,
                                 filter_type=kw.get("filter_type", "lowpass"),
                                 cutoff=kw.get("cutoff_hz", 1000),
                                 resonance=kw.get("resonance", 1.0), sr=sr,
                                 zi=zi)
        # resonant_filter returns (array, zf) when zi is not None,
        # or just array when zi is None (first call)
        if isinstance(result, tuple):
            res, zf = result
            if zf is not None:
                state["filter_zi"] = zf
            return res
        else:
            return result
    else:
        # Stateless mode: simple call
        return resonant_filter(audio_data, start, end,
                               filter_type=kw.get("filter_type", "lowpass"),
                               cutoff=kw.get("cutoff_hz", 1000),
                               resonance=kw.get("resonance", 1.0), sr=sr)

def _w_pan(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Pan."""
    from core.effects.pan import pan_stereo
    return pan_stereo(audio_data, start, end,
                      pan=kw.get("pan", 0.0), mono=kw.get("mono", False))

def _w_pitch_shift(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Pitch Shift."""
    from core.effects.pitch_shift import pitch_shift, pitch_shift_simple
    if kw.get("simple", False):
        return pitch_shift_simple(audio_data, start, end,
                                  semitones=kw.get("semitones", 0))
    return pitch_shift(audio_data, start, end,
                       semitones=kw.get("semitones", 0), sr=sr)

def _w_time_stretch(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Time Stretch."""
    from core.effects.time_stretch import time_stretch
    return time_stretch(audio_data, start, end, factor=kw.get("factor", 1.0))

def _w_tape_stop(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Tape Stop."""
    from core.effects.tape_stop import tape_stop
    duration_ms = kw.get("duration_ms", 1500)
    seg_len = end - start
    duration_pct = min(1.0, max(0.05, (duration_ms / 1000.0) * sr / seg_len)) if seg_len > 0 else 0.5
    return tape_stop(audio_data, start, end, duration_pct=duration_pct, sr=sr)

def _w_saturation(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Saturation."""
    from core.effects.saturation import saturate
    return saturate(audio_data, start, end,
                    mode=kw.get("type", "soft"),
                    drive=kw.get("drive", 3.0),
                    tone=kw.get("tone", 0.5),
                    sr=sr)

def _w_distortion(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Distortion."""
    from core.effects.distortion import distortion
    return distortion(audio_data, start, end,
                      drive=kw.get("drive", 5.0),
                      tone=kw.get("tone", 0.5),
                      mode=kw.get("mode", "tube"))

def _w_bitcrusher(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Bitcrusher."""
    from core.effects.bitcrusher import bitcrush
    return bitcrush(audio_data, start, end,
                    bit_depth=kw.get("bit_depth", 8),
                    downsample=kw.get("downsample", 1))

def _w_chorus(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Chorus."""
    from core.effects.chorus import chorus
    return chorus(audio_data, start, end,
                  depth_ms=kw.get("depth_ms", 3.0),
                  rate_hz=kw.get("rate_hz", 1.5),
                  mix=kw.get("mix", 0.5),
                  voices=kw.get("voices", 2), sr=sr)

def _w_phaser(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Phaser."""
    from core.effects.phaser import phaser
    return phaser(audio_data, start, end,
                  rate_hz=kw.get("rate_hz", 0.5),
                  depth=kw.get("depth", 0.7),
                  stages=kw.get("stages", 4),
                  mix=kw.get("mix", 0.5), sr=sr)

def _w_tremolo(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Tremolo."""
    from core.effects.tremolo import tremolo
    return tremolo(audio_data, start, end,
                   rate_hz=kw.get("rate_hz", 5.0),
                   depth=kw.get("depth", 0.7),
                   shape=kw.get("shape", "sine"), sr=sr)

def _w_ring_mod(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Ring Modulator."""
    from core.effects.ring_mod import ring_mod
    return ring_mod(audio_data, start, end,
                    freq=kw.get("frequency", 440),
                    mix=kw.get("mix", 0.5), sr=sr)

def _w_delay(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Delay."""
    from core.effects.delay import delay
    return delay(audio_data, start, end,
                 delay_ms=kw.get("delay_ms", 250),
                 feedback=kw.get("feedback", 0.4),
                 mix=kw.get("mix", 0.5), sr=sr)

def _w_vinyl(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Vinyl Crackle."""
    from core.effects.vinyl import vinyl
    amount = kw.get("amount", 0.5)
    return vinyl(audio_data, start, end,
                 crackle=amount, noise=amount * 0.5, wow=amount * 0.3, sr=sr)

def _w_ott(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet OTT Compression."""
    from core.effects.ott import ott
    return ott(audio_data, start, end, depth=kw.get("depth", 0.5), sr=sr)

def _w_stutter(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Stutter."""
    from core.effects.stutter import stutter
    return stutter(audio_data, start, end,
                   repeats=kw.get("repeats", 4),
                   decay=kw.get("decay", 0.0),
                   stutter_mode=kw.get("stutter_mode", "normal"))

def _w_granular(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Granular."""
    from core.effects.granular import granular
    return granular(audio_data, start, end,
                    grain_size_ms=kw.get("grain_ms", 50),
                    density=kw.get("density", 4),
                    randomize=kw.get("chaos", 0.5), sr=sr)

def _w_shuffle(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Shuffle."""
    from core.effects.shuffle import shuffle
    return shuffle(audio_data, start, end, slices=kw.get("num_slices", 8))

def _w_buffer_freeze(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Buffer Freeze."""
    from core.effects.buffer_freeze import buffer_freeze
    return buffer_freeze(audio_data, start, end,
                         grain_ms=kw.get("buffer_ms", 50), sr=sr)

def _w_datamosh(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Datamosh."""
    from core.effects.datamosh import datamosh
    return datamosh(audio_data, start, end,
                    intensity=kw.get("chaos", 0.5),
                    block_size=kw.get("block_size", 512))

def _w_wave_ondulee(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l'effet Wave Ondulée."""
    from core.effects.wave_ondulee import wave_ondulee
    return wave_ondulee(audio_data, start, end, sr=sr,
                        speed=kw.get("speed", 3.0),
                        pitch_depth=kw.get("pitch_depth", 0.4),
                        vol_depth=kw.get("vol_depth", 0.3),
                        stereo_offset=kw.get("stereo_offset", True))


def _w_robot(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Robotic."""
    from core.effects.robot import robot
    return robot(audio_data, start, end, sr=sr,
                 grain_ms=kw.get("grain_ms", 8),
                 robot_amount=kw.get("robot_amount", 0.7),
                 metallic=kw.get("metallic", 0.4),
                 monotone=kw.get("monotone", 0.0),
                 pitch_hz=kw.get("pitch_hz", 150))

def _w_digital_noise(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Digital Noise."""
    from core.effects.digital_noise import digital_noise
    return digital_noise(audio_data, start, end, sr=sr,
                         bit_reduction=kw.get("bit_reduction", 0.5),
                         noise_amount=kw.get("noise_amount", 0.3),
                         sample_hold=kw.get("sample_hold", 1))

def _w_tape_glitch(audio_data, start, end, sr=44100, **kw):
    """Wrapper : applique l effet Tape Glitch."""
    from core.effects.tape_glitch import tape_glitch
    return tape_glitch(audio_data, start, end, sr=sr,
                       glitch_rate=kw.get("glitch_rate", 0.4),
                       dropout_chance=kw.get("dropout_chance", 0.15),
                       wow=kw.get("wow", 0.3),
                       flutter=kw.get("flutter", 0.4),
                       noise=kw.get("noise", 0.1))


# ═══ Section ordering ═══

SECTION_ORDER = [
    "Glitch", "Basics", "Pitch & Time", "Distortion",
    "Modulation", "Space & Texture",
    "Custom",
]


def _define_plugins():
    """Definit les 28 plugins builtin avec leurs wrappers et dialogues."""
    from gui.effect_dialogs import (
        ReverseDialog, VolumeDialog, FilterDialog, PanDialog,
        PitchShiftDialog, TimeStretchDialog, TapeStopDialog,
        SaturationDialog, DistortionDialog, BitcrusherDialog,
        ChorusDialog, PhaserDialog, TremoloDialog, RingModDialog,
        DelayDialog, VinylDialog, OTTDialog,
        StutterDialog, GranularDialog, ShuffleDialog,
        BufferFreezeDialog, DatamoshDialog,
        WaveOnduleeDialog, RobotDialog, DigitalNoiseDialog,
        TapeGlitchDialog,
    )

    defs = [
        ("reverse",       "R", "#0f3460", "Basics",          "reverse",       ReverseDialog,      _w_reverse),
        ("volume",        "V", "#4cc9f0", "Basics",          "volume",        VolumeDialog,       _w_volume),
        ("filter",        "F", "#264653", "Basics",          "filter",        FilterDialog,       _w_filter),
        ("pan",           "P", "#2563eb", "Basics",          "pan",           PanDialog,          _w_pan),
        ("pitch_shift",   "P", "#16c79a", "Pitch & Time",    "pitch_shift",   PitchShiftDialog,   _w_pitch_shift),
        ("time_stretch",  "T", "#c74b50", "Pitch & Time",    "time_stretch",  TimeStretchDialog,  _w_time_stretch),
        ("tape_stop",     "T", "#3d5a80", "Pitch & Time",    "tape_stop",     TapeStopDialog,     _w_tape_stop),
        ("wave_ondulee",  "W", "#0ea5e9", "Pitch & Time",    "wave_ondulee",  WaveOnduleeDialog,  _w_wave_ondulee),
        ("saturation",    "S", "#ff6b35", "Distortion",      "saturation",    SaturationDialog,   _w_saturation),
        ("distortion",    "D", "#b5179e", "Distortion",      "distortion",    DistortionDialog,   _w_distortion),
        ("bitcrusher",    "B", "#533483", "Distortion",      "bitcrusher",    BitcrusherDialog,   _w_bitcrusher),
        ("chorus",        "C", "#2a6478", "Modulation",      "chorus",        ChorusDialog,       _w_chorus),
        ("phaser",        "P", "#6d597a", "Modulation",      "phaser",        PhaserDialog,       _w_phaser),
        ("tremolo",       "T", "#e07c24", "Modulation",      "tremolo",       TremoloDialog,      _w_tremolo),
        ("ring_mod",      "R", "#6d597a", "Modulation",      "ring_mod",      RingModDialog,      _w_ring_mod),
        ("delay",         "D", "#2a9d8f", "Space & Texture", "delay",         DelayDialog,        _w_delay),
        ("vinyl",         "V", "#606c38", "Space & Texture", "vinyl",         VinylDialog,        _w_vinyl),
        ("ott",           "O", "#e76f51", "Space & Texture", "ott",           OTTDialog,          _w_ott),
        ("robot",         "R", "#4a00e0", "Space & Texture", "robot",         RobotDialog,        _w_robot),
        ("digital_noise", "N", "#00c896", "Glitch",          "digital_noise", DigitalNoiseDialog, _w_digital_noise),
        ("stutter",       "S", "#e94560", "Glitch",          "stutter",       StutterDialog,      _w_stutter),
        ("granular",      "G", "#7b2d8e", "Glitch",          "granular",      GranularDialog,     _w_granular),
        ("shuffle",       "S", "#bb3e03", "Glitch",          "shuffle",       ShuffleDialog,      _w_shuffle),
        ("buffer_freeze", "B", "#457b9d", "Glitch",          "buffer_freeze", BufferFreezeDialog,  _w_buffer_freeze),
        ("datamosh",      "D", "#9b2226", "Glitch",          "datamosh",      DatamoshDialog,     _w_datamosh),
        ("tape_glitch",   "T", "#6b705c", "Glitch",          "tape_glitch",   TapeGlitchDialog,   _w_tape_glitch),
    ]
    plugins = {}
    for eid, icon, color, section, name_key, dlg, fn in defs:
        plugins[eid] = Plugin(eid, icon, color, section, name_key, dlg, fn)
    return plugins


_plugins_cache = None

def load_plugins(force_reload=False):
    """Charge tous les plugins (builtin + user) et retourne la liste."""
    global _plugins_cache
    if _plugins_cache is None or force_reload:
        _plugins_cache = _define_plugins()
        # Load user plugins and merge
        try:
            from plugins.user_loader import load_user_plugins
            user = load_user_plugins()
            _plugins_cache.update(user)
        except Exception as ex:
            _log.error("User plugins error: %s", ex)
    return _plugins_cache


def plugins_grouped(plugins, lang=None):
    """Retourne les plugins groupes par categorie pour le menu."""
    groups = {}
    for pid, plugin in plugins.items():
        groups.setdefault(plugin.section, []).append(plugin)
    result = []
    for sec in SECTION_ORDER:
        if sec in groups:
            result.append((sec, sorted(groups[sec], key=lambda p: p.get_name(lang))))
    for sec, plist in groups.items():
        if sec not in SECTION_ORDER:
            result.append((sec, sorted(plist, key=lambda p: p.get_name(lang))))
    return result
