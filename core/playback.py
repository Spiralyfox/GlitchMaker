"""Moteur de lecture audio — stream low-latency avec support metronome."""
import numpy as np
import sounddevice as sd
from core.metronome import Metronome


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
        """Cree ou recreee le stream de sortie avec les bons parametres (sr, channels)."""
        if self._stream is not None:
            try: self._stream.close()
            except: pass
            self._stream = None
        if self.audio_data is None or self.sample_rate <= 0:
            self._stream_sr = 0; self._stream_ch = 0; return
        ch = self.audio_data.shape[1] if self.audio_data.ndim > 1 else 1
        try:
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate, channels=ch, dtype="float32",
                callback=self._callback, blocksize=256, latency='low',
                device=self.output_device)
            self._stream.start()
            self._stream_sr = self.sample_rate
            self._stream_ch = ch
        except Exception as e:
            print(f"[playback] stream error: {e}")
            self._stream = None; self._stream_sr = 0; self._stream_ch = 0

    def _callback(self, outdata, frames, time_info, status):
        """Callback audio appele par sounddevice — remplit le buffer de sortie.
        Applique le volume, gere la fin de fichier / boucle, mixe le metronome."""
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
                if self.on_playback_finished: self.on_playback_finished()
            return
        # Copie des donnees audio avec ajustement des canaux
        data = self.audio_data[pos:end]
        if data.ndim == 1: data = data.reshape(-1, 1)
        if data.shape[1] < outdata.shape[1]:
            data = np.column_stack([data] * outdata.shape[1])
        elif data.shape[1] > outdata.shape[1]:
            data = data[:, :outdata.shape[1]]
        outdata[:valid] = data[:valid] * self.volume
        if valid < frames: outdata[valid:] = 0
        # Ajout des clics de metronome
        self.metronome.mix_into(outdata, pos, frames)
        self.position = end
        # Gestion de la boucle
        if self.looping and self.loop_end is not None and self.position >= self.loop_end:
            self.position = self.loop_start if self.loop_start is not None else 0

    def play(self, start_pos=None):
        """Demarre la lecture depuis start_pos (ou la position actuelle)."""
        if self.audio_data is None: return
        if start_pos is not None: self.position = start_pos
        self.is_playing = True; self.is_paused = False
        if self._stream is None: self._ensure_stream()

    def pause(self):
        """Met en pause la lecture."""
        self.is_playing = False; self.is_paused = True

    def stop(self):
        """Arrete la lecture et revient au debut."""
        self.is_playing = False; self.is_paused = False; self.position = 0

    def seek(self, pos):
        """Deplace la tete de lecture a la position donnee (en samples)."""
        self.position = max(0, min(pos, len(self.audio_data) - 1 if self.audio_data is not None else 0))

    def set_volume(self, v):
        """Change le volume de sortie (0.0-1.0)."""
        self.volume = max(0.0, min(1.0, v))

    def set_loop(self, start, end, looping=False):
        """Configure la boucle de lecture (debut, fin en samples)."""
        self.loop_start = start; self.loop_end = end; self.looping = looping

    def set_output_device(self, device_idx):
        """Change le peripherique de sortie audio et recreee le stream."""
        self.output_device = device_idx
        if self.audio_data is not None: self._ensure_stream()

    def set_input_device(self, device_idx):
        """Change le peripherique d'entree (pour enregistrement)."""
        self.input_device = device_idx

    def cleanup(self):
        """Ferme le stream audio proprement (appele a la fermeture)."""
        self.is_playing = False
        if self._stream:
            try: self._stream.close()
            except: pass
            self._stream = None

    def suspend_stream(self):
        """Suspend le stream (pour laisser sd.play faire la preview)."""
        self.is_playing = False
        if self._stream:
            try: self._stream.close()
            except: pass
            self._stream = None; self._stream_sr = 0; self._stream_ch = 0

    def resume_stream(self):
        """Restaure le stream apres une preview."""
        if self.audio_data is not None and self._stream is None:
            self._ensure_stream()
