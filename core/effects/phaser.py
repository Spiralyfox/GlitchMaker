"""Phaser — cascaded allpass filters with LFO, feedback, and stereo spread."""
import numpy as np


def phaser(audio_data: np.ndarray, start: int, end: int,
           rate_hz: float = 0.5, depth: float = 0.7,
           stages: int = 4, feedback: float = 0.0,
           mix: float = 0.7, sr: int = 44100) -> np.ndarray:
    """
    Phaser effect using cascaded first-order allpass filters with LFO.

    The classic phaser topology:
        input ──(+ fb)──▶ AP1 → AP2 → … → APn ──▶ output
                 ↑                                    │
                 └───────── feedback × gain ──────────┘

    Args:
        rate_hz: LFO speed (0.05–10 Hz)
        depth:   LFO depth (0–1) — controls sweep range
        stages:  allpass stages (1–12, more = deeper notches)
        feedback: chain output fed back into input (0–0.95)
        mix:     dry/wet mix (0–1)
        sr:      sample rate
    """
    out = audio_data.copy()
    seg = out[start:end].astype(np.float64)
    n = len(seg)

    if n == 0:
        return out

    mono_input = seg.ndim == 1
    if mono_input:
        seg = seg.reshape(-1, 1)
    channels = seg.shape[1]

    feedback = max(0.0, min(0.95, feedback))
    stages = max(1, min(12, stages))

    # LFO time array
    t_arr = np.arange(n, dtype=np.float64) / sr

    # Sweep range: map depth to frequency range within 100 Hz – 4 kHz
    min_freq = 100.0
    max_freq = min(4000.0, sr / 2 - 200)

    result = np.zeros_like(seg)

    for ch in range(channels):
        x = seg[:, ch].copy()

        # Stereo spread: 90° LFO phase offset between L and R
        phase_offset = ch * (np.pi * 0.5)

        # LFO → center frequency for allpass filters
        lfo = 0.5 * (1.0 + np.sin(2.0 * np.pi * rate_hz * t_arr + phase_offset))
        # Map to frequency range with depth control
        center_freqs = min_freq + (max_freq - min_freq) * depth * lfo

        # ── Sample-by-sample processing with proper feedback ──
        # State for each allpass stage
        ap_state = np.zeros(stages)  # one state per stage
        fb_sample = 0.0              # feedback from previous output

        y_out = np.zeros(n)

        for i in range(n):
            # Allpass coefficient from LFO
            freq = center_freqs[i]
            freq = max(20.0, min(freq, sr / 2 - 100))
            tan_w = np.tan(np.pi * freq / sr)
            a = (tan_w - 1.0) / (tan_w + 1.0)

            # Input + feedback
            inp = x[i] + fb_sample * feedback

            # Cascade through allpass stages
            sample = inp
            for s in range(stages):
                # First-order allpass: y[n] = a * x[n] + x[n-1] - a * y[n-1]
                # Using state variable form: state stores x[n-1] - a * y[n-1]
                ap_out = a * sample + ap_state[s]
                ap_state[s] = sample - a * ap_out
                sample = ap_out

            # Output of allpass chain
            fb_sample = sample
            y_out[i] = sample

        # Mix dry/wet
        result[:, ch] = seg[:, ch] * (1.0 - mix) + y_out * mix

    out_result = result.astype(np.float32)
    if mono_input:
        out_result = out_result.squeeze()
    out[start:end] = out_result
    return out
