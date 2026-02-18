"""
Delay Feedback — Echo avec feedback.
La queue du delay se mixe PAR-DESSUS l'audio existant qui suit la sélection,
au lieu de s'étendre dans le silence. Les échos se fondent naturellement
avec la suite du morceau.
"""

import numpy as np


def delay(audio_data: np.ndarray, start: int, end: int,
          delay_ms: float = 200.0, feedback: float = 0.6,
          mix: float = 0.5, sr: int = 44100) -> np.ndarray:
    """Applique un delay avec feedback.

    La queue des échos se superpose à l'audio existant après la sélection,
    permettant d'entendre les répétitions mélangées avec le contenu qui suit.
    Si la queue dépasse la fin du fichier, l'audio est étendu.

    Returns:
        ndarray potentiellement plus long que audio_data.
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

    # Build echo buffer (covers segment + tail)
    seg_len = len(segment)
    echo_len = seg_len + tail_samples

    if segment.ndim == 1:
        echo_buf = np.zeros(echo_len, dtype=np.float32)
    else:
        echo_buf = np.zeros((echo_len, segment.shape[1]), dtype=np.float32)

    # Place original dry signal
    echo_buf[:seg_len] = segment

    # Add echoes
    for i in range(1, n_echoes + 1):
        offset = i * delay_samples
        gain = feedback ** i
        if gain < 0.01:
            break
        echo_end = min(offset + seg_len, echo_len)
        echo_src_len = echo_end - offset
        if echo_src_len <= 0:
            break
        echo_buf[offset:echo_end] += segment[:echo_src_len] * gain

    # Mix dry/wet for the echo buffer
    dry_buf = np.zeros_like(echo_buf)
    dry_buf[:seg_len] = segment
    wet_result = dry_buf * (1.0 - mix) + echo_buf * mix

    # Trim silence from tail (below -60dB)
    threshold = 0.001
    if wet_result.ndim == 1:
        last_loud = np.where(np.abs(wet_result) > threshold)[0]
    else:
        last_loud = np.where(np.max(np.abs(wet_result), axis=1) > threshold)[0]

    if len(last_loud) > 0:
        trim_end = min(last_loud[-1] + sr // 4, len(wet_result))  # + 0.25s safety
        wet_result = wet_result[:trim_end]
    else:
        wet_result = wet_result[:seg_len]

    # ── Reassemble: mix the tail OVER the audio that follows ──
    result = audio_data.copy()
    before = result[:start]
    after = result[end:]

    # The wet_result has two parts:
    #   1. [0:seg_len] → replaces the original selection
    #   2. [seg_len:] → the echo tail, to be mixed OVER 'after'
    selection_part = wet_result[:seg_len]
    tail_part = wet_result[seg_len:] if len(wet_result) > seg_len else np.array([], dtype=np.float32)

    tail_len = len(tail_part)
    after_len = len(after)

    if tail_len == 0:
        # No tail — simple replacement
        result[start:end] = np.clip(selection_part, -1.0, 1.0)
        return result.astype(np.float32)

    if tail_len <= after_len:
        # Tail fits within existing 'after' — mix over it
        if after.ndim == 1 and tail_part.ndim == 1:
            after[:tail_len] = after[:tail_len] + tail_part
        elif after.ndim > 1 and tail_part.ndim > 1:
            after[:tail_len] = after[:tail_len] + tail_part
        elif after.ndim > 1 and tail_part.ndim == 1:
            for ch in range(after.shape[1]):
                after[:tail_len, ch] = after[:tail_len, ch] + tail_part
        else:
            after[:tail_len] = after[:tail_len] + tail_part

        parts = [before, np.clip(selection_part, -1.0, 1.0),
                 np.clip(after, -1.0, 1.0)]
    else:
        # Tail extends beyond existing audio — mix what overlaps, extend the rest
        if after_len > 0:
            overlap = tail_part[:after_len]
            if after.ndim == overlap.ndim:
                mixed_after = after + overlap
            elif after.ndim > 1 and overlap.ndim == 1:
                mixed_after = after.copy()
                for ch in range(after.shape[1]):
                    mixed_after[:, ch] = after[:, ch] + overlap
            else:
                mixed_after = after + overlap
            extension = tail_part[after_len:]
        else:
            mixed_after = np.array([], dtype=np.float32).reshape(0, *selection_part.shape[1:]) if selection_part.ndim > 1 else np.array([], dtype=np.float32)
            extension = tail_part

        parts = [before, np.clip(selection_part, -1.0, 1.0)]
        if len(mixed_after) > 0:
            parts.append(np.clip(mixed_after, -1.0, 1.0))
        if len(extension) > 0:
            parts.append(np.clip(extension, -1.0, 1.0))

    result = np.concatenate([p for p in parts if len(p) > 0], axis=0)
    return np.clip(result, -1.0, 1.0).astype(np.float32)
