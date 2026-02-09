"""
Autotune — Pitch correction to nearest note.
Adjustable speed (hard/soft tune), key, and scale.
"""
import numpy as np
from scipy.signal import resample

# Note frequencies A0 to C8
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_SCALES = {
    "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major":     [0, 2, 4, 5, 7, 9, 11],
    "minor":     [0, 2, 3, 5, 7, 8, 10],
    "pentatonic": [0, 2, 4, 7, 9],
    "blues":     [0, 3, 5, 6, 7, 10],
    "dorian":    [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}


def _freq_to_midi(f):
    """Convertit une frequence Hz en numero de note MIDI."""
    if f <= 0:
        return 0
    return 69 + 12 * np.log2(f / 440.0)


def _midi_to_freq(m):
    """Convertit un numero MIDI en frequence Hz."""
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _snap_to_scale(midi_note, key_offset, scale_intervals):
    """Snap a MIDI note to nearest note in the given scale + key."""
    note_class = int(round(midi_note)) % 12
    relative = (note_class - key_offset) % 12
    # Find closest scale degree
    best = min(scale_intervals, key=lambda s: min(abs(relative - s), 12 - abs(relative - s)))
    target_class = (best + key_offset) % 12
    octave = int(round(midi_note)) // 12
    target = octave * 12 + target_class
    # Pick closest octave
    if abs(target - midi_note) > abs(target + 12 - midi_note):
        target += 12
    elif abs(target - midi_note) > abs(target - 12 - midi_note):
        target -= 12
    return float(target)


def _detect_pitch_autocorr(frame, sr, fmin=80, fmax=800):
    """Simple autocorrelation pitch detection."""
    n = len(frame)
    if n < 64:
        return 0.0
    # Normalize
    frame = frame - np.mean(frame)
    if np.max(np.abs(frame)) < 1e-5:
        return 0.0
    # Autocorrelation via FFT
    fft_size = 1 << (2 * n - 1).bit_length()
    fft = np.fft.rfft(frame, fft_size)
    acf = np.fft.irfft(fft * np.conj(fft))[:n]
    # Normalize
    acf = acf / (acf[0] + 1e-12)
    # Search range
    min_lag = max(2, int(sr / fmax))
    max_lag = min(n - 1, int(sr / fmin))
    if min_lag >= max_lag:
        return 0.0
    search = acf[min_lag:max_lag]
    if len(search) == 0:
        return 0.0
    peak_idx = np.argmax(search)
    peak_val = search[peak_idx]
    if peak_val < 0.3:  # Not periodic enough
        return 0.0
    lag = peak_idx + min_lag
    if lag == 0:
        return 0.0
    # Parabolic interpolation
    if 0 < peak_idx < len(search) - 1:
        a, b, c = search[peak_idx - 1], search[peak_idx], search[peak_idx + 1]
        denom = 2 * (2 * b - a - c)
        if abs(denom) > 1e-10:
            offset = (a - c) / denom
            lag = peak_idx + min_lag + offset
    return sr / lag


def autotune(audio_data, start, end, sr=44100,
             speed=0.8, key="C", scale="chromatic", mix=1.0):
    """
    Pitch correction.
    speed: 0.0 = no correction, 1.0 = hard snap (T-Pain style)
    key: root note name
    scale: scale type
    mix: dry/wet
    """
    result = audio_data.copy()
    seg = result[start:end].copy().astype(np.float64)
    n = len(seg)
    if n < 512:
        return result

    is_stereo = seg.ndim == 2
    if is_stereo:
        mono = np.mean(seg, axis=1)
    else:
        mono = seg.copy()

    key_offset = _NOTE_NAMES.index(key) if key in _NOTE_NAMES else 0
    scale_intervals = _SCALES.get(scale, _SCALES["chromatic"])

    # Window parameters
    win_size = 2048
    hop = win_size // 4
    window = np.hanning(win_size)
    output = np.zeros_like(mono)
    weight = np.zeros(n, dtype=np.float64)

    for i in range(0, n - win_size, hop):
        frame = mono[i:i + win_size] * window
        freq = _detect_pitch_autocorr(frame, sr)
        if freq < 60 or freq > 1000:
            # No pitch detected / out of range — pass through
            output[i:i + win_size] += frame
            weight[i:i + win_size] += window
            continue

        midi = _freq_to_midi(freq)
        target_midi = _snap_to_scale(midi, key_offset, scale_intervals)
        shift_semitones = (target_midi - midi) * speed

        if abs(shift_semitones) < 0.05:
            output[i:i + win_size] += frame
            weight[i:i + win_size] += window
            continue

        # Pitch shift this frame
        factor = 2.0 ** (shift_semitones / 12.0)
        new_len = max(2, int(win_size / factor))
        shifted = resample(frame, new_len)
        shifted = resample(shifted, win_size)
        output[i:i + win_size] += shifted * window
        weight[i:i + win_size] += window

    # Normalize overlap-add
    weight = np.maximum(weight, 1e-8)
    output /= weight

    # Apply to original (with mix)
    dry = seg.copy()
    if is_stereo:
        # Apply same pitch correction ratio to both channels
        ratio = np.where(np.abs(mono) > 1e-6, output / (mono + 1e-8), 1.0)
        ratio = np.clip(ratio, -3.0, 3.0)
        for ch in range(seg.shape[1]):
            seg[:, ch] = seg[:, ch] * (1.0 - mix + mix * ratio)
    else:
        seg = mono * (1.0 - mix) + output * mix

    result[start:end] = seg.astype(np.float32)
    return np.clip(result, -1.0, 1.0)
