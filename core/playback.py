"""Playback engine — low-latency stream with metronome support."""
import numpy as np
import sounddevice as sd
from core.metronome import Metronome


class PlaybackEngine:
    def __init__(self):
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
        data = self.audio_data[pos:end]
        if data.ndim == 1: data = data.reshape(-1, 1)
        if data.shape[1] < outdata.shape[1]:
            data = np.column_stack([data] * outdata.shape[1])
        elif data.shape[1] > outdata.shape[1]:
            data = data[:, :outdata.shape[1]]
        outdata[:valid] = data[:valid] * self.volume
        if valid < frames: outdata[valid:] = 0
        self.metronome.mix_into(outdata, pos, frames)
        self.position = end
        if self.looping and self.loop_end is not None and self.position >= self.loop_end:
            self.position = self.loop_start if self.loop_start is not None else 0

    def play(self, start_pos=None):
        if self.audio_data is None: return
        if start_pos is not None: self.position = start_pos
        self.is_playing = True; self.is_paused = False
        if self._stream is None: self._ensure_stream()

    def pause(self): self.is_playing = False; self.is_paused = True
    def stop(self): self.is_playing = False; self.is_paused = False; self.position = 0

    def seek(self, pos):
        self.position = max(0, min(pos, len(self.audio_data) - 1 if self.audio_data is not None else 0))

    def set_volume(self, v): self.volume = max(0.0, min(1.0, v))
    def set_loop(self, start, end, looping=False):
        self.loop_start = start; self.loop_end = end; self.looping = looping

    def set_output_device(self, device_idx):
        self.output_device = device_idx
        if self.audio_data is not None: self._ensure_stream()

    def set_input_device(self, device_idx): self.input_device = device_idx

    def cleanup(self):
        self.is_playing = False
        if self._stream:
            try: self._stream.close()
            except: pass
            self._stream = None

    def suspend_stream(self):
        self.is_playing = False
        if self._stream:
            try: self._stream.close()
            except: pass
            self._stream = None; self._stream_sr = 0; self._stream_ch = 0

    def resume_stream(self):
        if self.audio_data is not None and self._stream is None:
            self._ensure_stream()
