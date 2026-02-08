"""Preview player — plays short MP3 previews of effects."""

import os
import threading

_playing = False
_stop_flag = False


def is_playing() -> bool:
    """Retourne True si une preview est en cours."""
    return _playing


def stop_preview():
    """Arrete la preview en cours."""
    global _stop_flag
    _stop_flag = True


def play_preview(filepath: str):
    """Play a preview file in a background thread."""
    global _playing, _stop_flag
    if not filepath or not os.path.isfile(filepath):
        return
    if os.path.getsize(filepath) < 100:
        return  # empty placeholder

    _stop_flag = False

    def _run():
        """Thread de lecture de preview via sd.play()."""
        global _playing, _stop_flag
        _playing = True
        try:
            import sounddevice as sd
            import soundfile as sf
            data, sr = sf.read(filepath, dtype="float32")
            sd.play(data, sr)
            sd.wait()
        except Exception as ex:
            print(f"[preview] {ex}")
        finally:
            _playing = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
