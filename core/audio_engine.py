"""
Audio engine — multi-format loading, export.
MP3 export: lameenc (pure Python, no ffmpeg) > ffmpeg > pydub.
Other formats: soundfile > ffmpeg > pydub > librosa.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import glob
import numpy as np
import soundfile as sf


# ═══════════════════════════════════════
# FFmpeg detection + auto-download
# ═══════════════════════════════════════

_ffmpeg_cache = None
_ffmpeg_searched = False

# Directory where we store our own ffmpeg copy
_FFMPEG_DIR = os.path.join(os.path.expanduser("~"), ".glitchmaker", "ffmpeg")

# Static build download URLs (well-known, stable sources)
_FFMPEG_URLS = {
    "win64": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "linux64": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    "macos": "https://evermeet.cx/ffmpeg/ffmpeg-7.1.1.zip",
}


def _our_ffmpeg_path() -> str:
    """Path where we store our downloaded ffmpeg."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    return os.path.join(_FFMPEG_DIR, name)


def _load_ffmpeg_from_settings():
    """Try loading ffmpeg path from saved settings."""
    global _ffmpeg_cache, _ffmpeg_searched
    try:
        settings_path = os.path.join(os.path.expanduser("~"), ".glitchmaker_settings.json")
        if os.path.isfile(settings_path):
            import json as _json
            with open(settings_path, "r", encoding="utf-8") as f:
                s = _json.load(f)
            custom = s.get("ffmpeg_path", "")
            if custom and os.path.isfile(custom):
                _ffmpeg_cache = custom
                _ffmpeg_searched = True
                return True
    except Exception:
        pass
    return False


# Try settings first at import time
_load_ffmpeg_from_settings()


def _find_ffmpeg() -> str | None:
    """Cherche FFmpeg dans le PATH et les emplacements courants."""
    global _ffmpeg_cache, _ffmpeg_searched
    if _ffmpeg_searched:
        return _ffmpeg_cache
    _ffmpeg_searched = True

    # 0. Our own downloaded copy
    our = _our_ffmpeg_path()
    if os.path.isfile(our):
        _ffmpeg_cache = our
        return our

    # 1. PATH
    path = shutil.which("ffmpeg")
    if path:
        _ffmpeg_cache = path
        return path

    # 2. Next to the app exe (PyInstaller or dev)
    app_dirs = []
    if getattr(sys, 'frozen', False):
        app_dirs.append(os.path.dirname(sys.executable))
    if sys.argv:
        app_dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    app_dirs.append(os.getcwd())
    for d in app_dirs:
        for name in ("ffmpeg.exe", "ffmpeg"):
            for sub in ["", os.path.join("ffmpeg", "bin")]:
                p = os.path.join(d, sub, name) if sub else os.path.join(d, name)
                if os.path.isfile(p):
                    _ffmpeg_cache = p
                    return p

    if os.name != 'nt':
        for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg",
                  os.path.expanduser("~/.local/bin/ffmpeg")]:
            if os.path.isfile(p):
                _ffmpeg_cache = p
                return p
        return None

    # ── Windows-specific search ──
    try:
        r = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True, timeout=5,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if line and os.path.isfile(line):
                    _ffmpeg_cache = line
                    return line
    except Exception:
        pass

    candidates = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links", "ffmpeg.exe"))
        pkg_dir = os.path.join(local, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(pkg_dir):
            candidates.extend(glob.glob(os.path.join(pkg_dir, "**", "ffmpeg.exe"), recursive=True))

    for drive in ["C:", "D:"]:
        for sub in [r"\ffmpeg\bin", r"\ffmpeg", r"\Program Files\ffmpeg\bin",
                    r"\Program Files (x86)\ffmpeg\bin", r"\Tools\ffmpeg\bin"]:
            candidates.append(f"{drive}{sub}\\ffmpeg.exe")

    user_home = os.path.expanduser("~")
    candidates.append(os.path.join(user_home, "scoop", "shims", "ffmpeg.exe"))
    candidates.append(os.path.join(user_home, "scoop", "apps", "ffmpeg", "current", "bin", "ffmpeg.exe"))
    candidates.append(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe")

    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d.strip():
            candidates.append(os.path.join(d.strip(), "ffmpeg.exe"))

    for folder in ["Downloads", "Desktop"]:
        fd = os.path.join(user_home, folder)
        if os.path.isdir(fd):
            candidates.extend(glob.glob(os.path.join(fd, "ffmpeg*", "**", "ffmpeg.exe"), recursive=True))

    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        try:
            if os.path.isfile(p):
                _ffmpeg_cache = p
                return p
        except Exception:
            pass
    return None


def _sync_pydub_ffmpeg():
    """Configure pydub pour utiliser FFmpeg si disponible."""
    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        try:
            from pydub import AudioSegment
            AudioSegment.converter = ffmpeg
            d = os.path.dirname(ffmpeg)
            probe = os.path.join(d, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if os.path.isfile(probe):
                AudioSegment.ffprobe = probe
        except Exception:
            pass


def ffmpeg_available() -> bool:
    """Quick check: is ffmpeg ready to use?"""
    return _find_ffmpeg() is not None


def download_ffmpeg(progress_cb=None) -> str:
    """
    Download a static FFmpeg build to ~/.glitchmaker/ffmpeg/.
    progress_cb(message: str) is called with status updates.
    Returns the path to the ffmpeg binary.
    Raises RuntimeError on failure.
    """
    import urllib.request
    import zipfile
    import tarfile
    import platform

    global _ffmpeg_cache, _ffmpeg_searched

    dst = _our_ffmpeg_path()
    if os.path.isfile(dst):
        _ffmpeg_cache = dst
        _ffmpeg_searched = True
        return dst

    os.makedirs(_FFMPEG_DIR, exist_ok=True)

    # Determine platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        url = _FFMPEG_URLS["win64"]
    elif system == "linux":
        url = _FFMPEG_URLS["linux64"]
    elif system == "darwin":
        url = _FFMPEG_URLS["macos"]
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    # Download
    if progress_cb:
        progress_cb(f"Downloading FFmpeg ({system})...")

    tmp_archive = os.path.join(_FFMPEG_DIR, "_download_tmp")
    try:
        urllib.request.urlretrieve(url, tmp_archive)
    except Exception as e:
        _cleanup(tmp_archive)
        raise RuntimeError(f"Download failed: {e}")

    # Extract ffmpeg binary
    if progress_cb:
        progress_cb("Extracting FFmpeg...")

    try:
        if url.endswith(".zip"):
            _extract_from_zip(tmp_archive, dst, system)
        elif ".tar" in url:
            _extract_from_tar(tmp_archive, dst)
        else:
            raise RuntimeError(f"Unknown archive format: {url}")
    except Exception as e:
        _cleanup(tmp_archive)
        _cleanup(dst)
        raise RuntimeError(f"Extraction failed: {e}")

    _cleanup(tmp_archive)

    if not os.path.isfile(dst):
        raise RuntimeError("FFmpeg binary not found after extraction")

    # Make executable on Unix
    if os.name != "nt":
        os.chmod(dst, 0o755)

    # Verify it runs
    try:
        r = subprocess.run([dst, "-version"], capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode != 0:
            raise RuntimeError("FFmpeg exits with error")
    except subprocess.TimeoutExpired:
        pass  # Some systems are slow, but binary exists
    except FileNotFoundError:
        _cleanup(dst)
        raise RuntimeError("Extracted binary cannot run")

    _ffmpeg_cache = dst
    _ffmpeg_searched = True
    _sync_pydub_ffmpeg()

    if progress_cb:
        progress_cb("FFmpeg ready ✓")

    return dst


def _extract_from_zip(archive, dst, system):
    """Extract ffmpeg binary from a zip archive."""
    import zipfile
    target = "ffmpeg.exe" if system == "windows" else "ffmpeg"
    with zipfile.ZipFile(archive) as zf:
        # Find the ffmpeg binary inside the zip (may be in a subfolder)
        candidates = [n for n in zf.namelist()
                      if n.endswith(f"/{target}") or n.endswith(f"\\{target}")
                      or n == target]
        # Prefer bin/ path
        best = None
        for c in candidates:
            if "/bin/" in c or "\\bin\\" in c:
                best = c
                break
        if not best and candidates:
            best = candidates[0]
        if not best:
            raise RuntimeError(f"'{target}' not found in zip")

        with zf.open(best) as src, open(dst, "wb") as out:
            out.write(src.read())


def _extract_from_tar(archive, dst):
    """Extract ffmpeg binary from a tar(.xz) archive."""
    import tarfile
    with tarfile.open(archive) as tf:
        candidates = [m for m in tf.getmembers()
                      if m.name.endswith("/ffmpeg") and m.isfile()]
        if not candidates:
            candidates = [m for m in tf.getmembers()
                          if m.name == "ffmpeg" and m.isfile()]
        if not candidates:
            raise RuntimeError("'ffmpeg' not found in tar archive")

        best = candidates[0]
        src = tf.extractfile(best)
        if src is None:
            raise RuntimeError("Cannot read ffmpeg from archive")
        with open(dst, "wb") as out:
            out.write(src.read())


def _cleanup(path):
    """Remove a file silently."""
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


# ═══════════════════════════════════════
# Loading
# ═══════════════════════════════════════

def load_audio(filepath: str) -> tuple[np.ndarray, int]:
    """Charge un fichier audio et retourne (numpy_array, sample_rate)."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    ext = os.path.splitext(filepath)[1].lower()
    errors = []

    # 1. soundfile (WAV, FLAC, OGG, AIFF)
    if ext in (".wav", ".flac", ".ogg", ".aiff"):
        try:
            data, sr = sf.read(filepath, dtype="float32", always_2d=True)
            return _ensure_stereo(data), sr
        except Exception as e:
            errors.append(f"soundfile: {e}")

    # 2. ffmpeg subprocess
    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            cmd = [ffmpeg, "-y", "-i", filepath, "-acodec", "pcm_s16le",
                   "-ar", "44100", "-ac", "2", tmp.name]
            subprocess.run(cmd, capture_output=True, check=True, timeout=30,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            data, sr = sf.read(tmp.name, dtype="float32", always_2d=True)
            os.unlink(tmp.name)
            return _ensure_stereo(data), sr
        except Exception as e:
            errors.append(f"ffmpeg: {e}")
            if tmp:
                try: os.unlink(tmp.name)
                except Exception: pass

    # 3. pydub
    try:
        _sync_pydub_ffmpeg()
        from pydub import AudioSegment
        seg = AudioSegment.from_file(filepath)
        sr = seg.frame_rate
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
        samples /= float(2 ** (seg.sample_width * 8 - 1))
        samples = samples.reshape(-1, seg.channels)
        return _ensure_stereo(samples), sr
    except Exception as e:
        errors.append(f"pydub: {e}")

    # 4. librosa
    try:
        import librosa
        y, sr = librosa.load(filepath, sr=None, mono=False)
        if y.ndim == 1:
            data = np.column_stack([y, y])
        else:
            data = y.T
        return _ensure_stereo(data.astype(np.float32)), sr
    except Exception as e:
        errors.append(f"librosa: {e}")

    # Build helpful error
    fname = os.path.basename(filepath)
    needs_ffmpeg = ext in (".mp3", ".m4a", ".aac", ".wma", ".opus")
    if needs_ffmpeg:
        # Try auto-downloading ffmpeg right now
        try:
            download_ffmpeg()
            # Retry load with ffmpeg now available
            return load_audio(filepath)
        except Exception:
            pass
        raise RuntimeError(
            f"Cannot load '{fname}'.\n\n"
            f"{ext.upper()} files require FFmpeg to decode.\n\n"
            f"Auto-download failed. Check your internet connection\n"
            f"and try again, or load WAV/FLAC files instead."
        )
    raise RuntimeError(
        f"Cannot load '{fname}'.\n\n"
        + "\n".join(errors)
    )


# ═══════════════════════════════════════
# Export
# ═══════════════════════════════════════

def export_wav(data: np.ndarray, sr: int, filepath: str):
    """Exporte un tableau numpy en fichier WAV."""
    sf.write(filepath, data, sr, subtype="PCM_16")


def _export_mp3_lameenc(data: np.ndarray, sr: int, filepath: str):
    """Pure Python MP3 export using lameenc — no ffmpeg needed."""
    import lameenc

    # Convert float32 stereo to interleaved int16
    clipped = np.clip(data, -1.0, 1.0)
    pcm_int16 = (clipped * 32767).astype(np.int16)
    pcm_bytes = pcm_int16.tobytes()

    channels = data.shape[1] if data.ndim > 1 else 1

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(192)
    encoder.set_in_sample_rate(sr)
    encoder.set_channels(channels)
    encoder.set_quality(2)  # 2=high quality, 7=fast

    mp3_data = encoder.encode(pcm_bytes)
    mp3_data += encoder.flush()

    with open(filepath, "wb") as f:
        f.write(mp3_data)


def export_audio(data: np.ndarray, sr: int, filepath: str, fmt: str = "wav"):
    """Exporte en MP3 ou FLAC via FFmpeg/pydub."""
    if fmt == "wav":
        export_wav(data, sr, filepath)
        return

    # FLAC: soundfile native — no ffmpeg needed
    if fmt == "flac":
        try:
            sf.write(filepath, data, sr, format="FLAC")
            return
        except Exception:
            pass

    # MP3: try lameenc first (pure Python, always works)
    if fmt == "mp3":
        try:
            _export_mp3_lameenc(data, sr, filepath)
            if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
                return
        except ImportError:
            pass  # lameenc not installed, fall through to ffmpeg
        except Exception as e:
            pass  # encoding failed, try ffmpeg

    if fmt not in ("mp3", "ogg"):
        raise ValueError(f"Unsupported format: {fmt}")

    # ffmpeg path
    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            export_wav(data, sr, tmp.name)
            codec = {"mp3": "libmp3lame", "ogg": "libvorbis"}[fmt]
            cmd = [ffmpeg, "-y", "-i", tmp.name, "-acodec", codec]
            if fmt == "mp3":
                cmd.extend(["-b:a", "192k"])
            cmd.append(filepath)
            result = subprocess.run(
                cmd, capture_output=True, timeout=60,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode == 0 and os.path.isfile(filepath):
                os.unlink(tmp.name)
                return
        except Exception:
            pass
        finally:
            if tmp:
                try: os.unlink(tmp.name)
                except Exception: pass

    # pydub fallback
    tmp = None
    try:
        _sync_pydub_ffmpeg()
        from pydub import AudioSegment
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        export_wav(data, sr, tmp.name)
        AudioSegment.from_wav(tmp.name).export(filepath, format=fmt)
        os.unlink(tmp.name)
        if os.path.isfile(filepath):
            return
    except Exception:
        if tmp:
            try: os.unlink(tmp.name)
            except Exception: pass

    # Auto-download ffmpeg and retry
    try:
        download_ffmpeg()
        # Retry now that ffmpeg is available
        return export_audio(data, sr, filepath)
    except Exception:
        pass

    raise RuntimeError(
        f"Cannot export to {fmt.upper()}.\n\n"
        f"FFmpeg is required for {fmt.upper()} export.\n\n"
        f"Auto-download failed. Check your internet connection\n"
        f"and try again."
    )


# ═══════════════════════════════════════
# Utilities
# ═══════════════════════════════════════

def _ensure_stereo(data: np.ndarray) -> np.ndarray:
    """Convertit mono en stereo si necessaire."""
    if data.ndim == 1:
        return np.column_stack([data, data]).astype(np.float32)
    if data.shape[1] == 1:
        return np.column_stack([data[:, 0], data[:, 0]]).astype(np.float32)
    out = data[:, :2]
    if out.dtype != np.float32:
        out = out.astype(np.float32)
    return out


def ensure_stereo(data: np.ndarray) -> np.ndarray:
    """Convertit mono en stereo si necessaire (public)."""
    return _ensure_stereo(data)


def audio_to_mono(data: np.ndarray) -> np.ndarray:
    """Convertit un signal stereo en mono (moyenne des canaux)."""
    if data.ndim == 1:
        return data.astype(np.float32)
    return np.mean(data, axis=1).astype(np.float32)


def get_duration(data: np.ndarray, sr: int) -> float:
    """Retourne la duree en secondes d un tableau audio."""
    return len(data) / sr


def format_time(seconds: float) -> str:
    """Formate une duree en secondes vers MM:SS.cc."""
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"
