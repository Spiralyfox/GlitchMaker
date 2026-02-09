"""
Delay Feedback — Echo avec feedback et queue de reverb.
Le delay etend l'audio au-dela de la selection pour que la queue soit audible.
"""

import numpy as np


def delay(audio_data: np.ndarray, start: int, end: int,
          delay_ms: float = 200.0, feedback: float = 0.6,
          mix: float = 0.5, sr: int = 44100) -> np.ndarray:
    """Applique un delay avec feedback. Retourne un segment PLUS LONG
    que l'original si la queue du delay depasse la fin de la selection.

    Returns:
        ndarray potentiellement plus long que audio_data[start:end].
    """
    segment = audio_data[start:end].copy()
    if len(segment) == 0:
        return audio_data.copy()

    delay_samples = max(1, int(delay_ms * sr / 1000.0))
    feedback = max(0.0, min(0.95, feedback))

    # Calculate how many echoes are audible
    n_echoes = int(np.log(0.01) / np.log(max(feedback, 0.01))) + 1
    n_echoes = min(n_echoes, 30)

    # Total tail length = last echo position
    tail_samples = n_echoes * delay_samples
    total_len = len(segment) + tail_samples

    # Create extended output buffer
    if segment.ndim == 1:
        output = np.zeros(total_len, dtype=np.float32)
    else:
        output = np.zeros((total_len, segment.shape[1]), dtype=np.float32)

    # Place original dry signal
    output[:len(segment)] = segment

    # Add echoes — each extends into the tail
    for i in range(1, n_echoes + 1):
        offset = i * delay_samples
        gain = feedback ** i
        if gain < 0.01:
            break
        echo_end = min(offset + len(segment), total_len)
        echo_src_len = echo_end - offset
        if echo_src_len <= 0:
            break
        output[offset:echo_end] += segment[:echo_src_len] * gain

    # Mix: dry (original padded) + wet (output with echoes)
    dry = np.zeros_like(output)
    dry[:len(segment)] = segment
    result = dry * (1.0 - mix) + output * mix

    # Trim silence from end (below -60dB)
    threshold = 0.001
    if result.ndim == 1:
        last_loud = np.where(np.abs(result) > threshold)[0]
    else:
        last_loud = np.where(np.max(np.abs(result), axis=1) > threshold)[0]

    if len(last_loud) > 0:
        trim_end = min(last_loud[-1] + sr // 4, len(result))  # + 0.25s safety
        result = result[:trim_end]

    return np.clip(result, -1.0, 1.0).astype(np.float32)
