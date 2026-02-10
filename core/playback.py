"""Moteur de lecture audio — stream low-latency avec support metronome."""
import numpy as np
import sounddevice as sd
from core.metronome import Metronome
from utils.logger import get_logger

_log = get_logger("playback")


class PlaybackEngine:
    """Gere la lecture audio en temps reel via un OutputStream sounddevice.
    Blocksize 256 (~6ms de latence). Supporte boucle, volume, metronome."""

    def __init__(self):
        """Initialise l'engine sans audio charge."""
        self.audio_data: np.ndarray | None = None
        self.sample_rate: int = 44100
        self.position: int = 0
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.volume: float = 0.8
        self.output_device = None
        self.input_device = None
        self._stream = None
        self._stream_sr = 0
        self._stream_ch = 0
        self.on_playback_finished = None
        self.loop_start: int | None = None
        self.loop_end: int | None = None
        self.looping: bool = False
        self.metronome = Metronome()

    def load(self, audio_data: np.ndarray, sr: int):
        """Charge un tableau numpy audio et prepare le stream de sortie."""
        if audio_data is not None and audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        self.audio_data = audio_data
        self.sample_rate = sr
        self.position = 0
        self.is_playing = False
        self.is_paused = False
        self.metronome.set_sr(sr)
        ch = audio_data.shape[1] if audio_data is not None and audio_data.ndim > 1 else 1
        if sr != self._stream_sr or ch != self._stream_ch or self._stream is None:
            self._ensure_stream()

    def _ensure_stream(self):
        """Crée ou recrée le stream de sortie avec les bons paramètres (sr, channels)."""
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception as ex:
                _log.debug("Stream close: %s", ex)
            self._stream = None
        if self.audio_data is None or self.sample_rate <= 0:
            self._stream_sr = 0; self._stream_ch = 0; return
        ch = self.audio_data.shape[1] if self.audio_data.ndim > 1 else 1
        device = self.output_device

        # Try progressively safer stream configs
        configs = [
            (device, 256, 'low'),      # Best latency
            (device, 512, 'low'),      # Medium
            (device, 1024, 'high'),    # Safe
            (None,   512, 'low'),      # System default, medium
            (None,   1024, 'high'),    # System default, safe
        ]
        for dev, bs, lat in configs:
            try:
                self._stream = sd.OutputStream(
                    samplerate=self.sample_rate, channels=ch, dtype="float32",
                    callback=self._callback, blocksize=bs, latency=lat,
                    device=dev)
                self._stream.start()
                self._stream_sr = self.sample_rate
                self._stream_ch = ch
                if dev != device:
                    self.output_device = dev
                _log.info("Audio stream: device=%s bs=%d lat=%s", dev, bs, lat)
                return
            except Exception as e:
                _log.debug("Stream config failed (dev=%s bs=%d lat=%s): %s", dev, bs, lat, e)
                if self._stream:
                    try: self._stream.close()
                    except: pass
                    self._stream = None

        _log.error("All stream configs failed")
        self._stream = None; self._stream_sr = 0; self._stream_ch = 0

    def refresh_device(self):
        """Re-create stream with current device (call after device change or hot-plug)."""
        if self.audio_data is not None:
            was_playing = self.is_playing
            pos = self.position
            self.is_playing = False
            self._ensure_stream()
            if was_playing:
                self.position = pos
                self.is_playing = True

    def _callback(self, outdata, frames, time_info, status):
        """Callback audio appele par sounddevice — remplit le buffer de sortie.
        Applique le volume, gere la fin de fichier / boucle, mixe le metronome."""
        try:
            if not self.is_playing or self.audio_data is None:
                outdata[:] = 0; return
            n = len(self.audio_data)
            pos = self.position
            end = min(pos + frames, n)
            valid = end - pos
            if valid <= 0:
                outdata[:] = 0
                if self.looping and self.loop_start is not None:
                    self.position = self.loop_start
                else:
                    self.is_playing = False
                    if self.on_playback_finished:
                        try: self.on_playback_finished()
                        except Exception: pass
                return
            data = self.audio_data[pos:end]
            if data.ndim == 1: data = data.reshape(-1, 1)
            out_ch = outdata.shape[1] if outdata.ndim > 1 else 1
            if data.shape[1] < out_ch:
                data = np.column_stack([data] * out_ch)
            elif data.shape[1] > out_ch:
                data = data[:, :out_ch]
            outdata[:valid] = data[:valid] * self.volume
            if valid < frames: outdata[valid:] = 0
            self.metronome.mix_into(outdata, pos, frames)
            self.position = end
            if self.looping and self.loop_end is not None and self.position >= self.loop_end:
                self.position = self.loop_start if self.loop_start is not None else 0
        except Exception:
            outdata[:] = 0

    def play(self, start_pos=None):
        """Demarre la lecture depuis start_pos (ou la position actuelle)."""
        if self.audio_data is None: return
        if start_pos is not None: self.position = start_pos
        self.looping = False
        self.loop_start = None
        self.loop_end = None
        # Ensure stream is ready BEFORE setting is_playing for instant start
        if self._stream is None: self._ensure_stream()
        self.is_playing = True; self.is_paused = False

    def pause(self):
        """Met en pause la lecture."""
        self.is_playing = False; self.is_paused = True

    def stop(self):
        """Arrete la lecture et revient au debut."""
        self.is_playing = False; self.is_paused = False; self.position = 0
        self.loop_start = None; self.loop_end = None; self.looping = False

    def seek(self, pos):
        """Déplace la tête de lecture à la position donnée (en samples)."""
        self.position = max(0, min(pos, len(self.audio_data) - 1 if self.audio_data is not None else 0))

    def set_volume(self, v):
        """Change le volume de sortie (0.0-1.0)."""
        self.volume = max(0.0, min(1.0, v))

    def set_loop(self, start, end, looping=False):
        """Configure la boucle de lecture (debut, fin en samples)."""
        self.loop_start = start; self.loop_end = end; self.looping = looping

    def set_output_device(self, device_idx):
        """Change le périphérique de sortie audio et recrée le stream."""
        self.output_device = device_idx
        if self.audio_data is not None: self._ensure_stream()

    def set_input_device(self, device_idx):
        """Change le peripherique d'entree (pour enregistrement)."""
        self.input_device = device_idx

    def cleanup(self):
        """Ferme le stream audio proprement (appele a la fermeture)."""
        self.is_playing = False
        if self._stream:
            try:
                self._stream.close()
            except Exception as ex:
                _log.debug("Cleanup stream close: %s", ex)
            self._stream = None

    def suspend_stream(self):
        """Suspend le stream (pour laisser sd.play faire la preview)."""
        self.is_playing = False
        if self._stream:
            try:
                self._stream.close()
            except Exception as ex:
                _log.debug("Suspend stream close: %s", ex)
            self._stream = None; self._stream_sr = 0; self._stream_ch = 0

    def resume_stream(self):
        """Restaure le stream apres une preview."""
        try:
            if self.audio_data is not None and self._stream is None:
                self._ensure_stream()
        except Exception as ex:
            _log.warning("Resume stream error: %s", ex)

    # ── Properties used by main_window ──

    @property
    def current_position(self):
        """Position actuelle de lecture en samples."""
        return self.position

    @current_position.setter
    def current_position(self, val):
        self.position = val

    @property
    def bpm(self):
        return self.metronome.bpm

    @bpm.setter
    def bpm(self, val):
        self.metronome.set_bpm(val)

    @property
    def metronome_on(self):
        return self.metronome.enabled

    @metronome_on.setter
    def metronome_on(self, val):
        self.metronome.enabled = val

    @property
    def metronome_vol(self):
        return self.metronome.volume

    @metronome_vol.setter
    def metronome_vol(self, val):
        self.metronome.set_volume(val)

    def toggle_metronome(self, bpm=None):
        """Active/desactive le metronome. Met a jour le BPM si fourni."""
        self.metronome.enabled = not self.metronome.enabled
        if bpm is not None:
            self.metronome.set_bpm(bpm)

    def resume(self):
        """Reprend la lecture apres une pause."""
        if self.audio_data is None:
            return
        if self._stream is None:
            self._ensure_stream()
        self.is_playing = True
        self.is_paused = False

    def play_selection(self, start, end):
        """Joue une selection audio (start/end en samples) en boucle."""
        if self.audio_data is None:
            return
        self.position = start
        self.loop_start = start
        self.loop_end = end
        self.looping = True
        if self._stream is None:
            self._ensure_stream()
        self.is_playing = True
        self.is_paused = False
