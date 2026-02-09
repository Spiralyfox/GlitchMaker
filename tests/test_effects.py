"""
Unit tests for all Glitch Maker audio effects.

Tests verify for each effect:
  1. Output is valid numpy array (no None)
  2. Output dtype is float32 or float64
  3. No NaN values in output
  4. No Inf values in output
  5. Output is clipped to [-1, 1] (or close)
  6. Output shape is compatible (same channels, reasonable length)

Run with:  python -m pytest tests/ -v
Or:        python -m unittest tests.test_effects -v
"""

import sys
import os
import unittest
import numpy as np

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Skip plugin tests if PyQt6 not available
try:
    import PyQt6
    HAS_QT = True
except ImportError:
    HAS_QT = False


def _make_test_signal(sr=44100, duration=0.5, channels=2, freq=440.0):
    """Generate a stereo sine wave test signal."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, dtype=np.float32)
    mono = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    if channels == 2:
        return np.column_stack([mono, mono * 0.8]).astype(np.float32)
    return mono


def _make_noise(sr=44100, duration=0.5, channels=2):
    """Generate stereo noise test signal."""
    rng = np.random.default_rng(42)
    n = int(sr * duration)
    if channels == 2:
        return (rng.uniform(-0.8, 0.8, (n, 2))).astype(np.float32)
    return (rng.uniform(-0.8, 0.8, n)).astype(np.float32)


class _EffectTestBase:
    """Mixin with common assertions for effect output validation."""

    def assert_valid_output(self, result, original, name="effect",
                            allow_length_change=False, max_amplitude=1.05):
        """Validate effect output meets all quality criteria."""
        # 1. Not None
        self.assertIsNotNone(result, f"{name}: returned None")
        # 2. Is numpy array
        self.assertIsInstance(result, np.ndarray, f"{name}: not ndarray")
        # 3. Valid dtype
        self.assertTrue(
            result.dtype in (np.float32, np.float64),
            f"{name}: unexpected dtype {result.dtype}")
        # 4. No NaN
        self.assertFalse(
            np.any(np.isnan(result)),
            f"{name}: contains {np.sum(np.isnan(result))} NaN values")
        # 5. No Inf
        self.assertFalse(
            np.any(np.isinf(result)),
            f"{name}: contains Inf values")
        # 6. Amplitude check
        max_val = np.max(np.abs(result))
        self.assertLessEqual(
            max_val, max_amplitude,
            f"{name}: amplitude {max_val:.4f} exceeds {max_amplitude}")
        # 7. Shape check
        if not allow_length_change:
            self.assertEqual(
                len(result), len(original),
                f"{name}: length changed {len(original)} → {len(result)}")
        if original.ndim > 1 and result.ndim > 1:
            self.assertEqual(
                result.shape[1], original.shape[1],
                f"{name}: channels changed {original.shape[1]} → {result.shape[1]}")
        # 8. Non-zero
        self.assertTrue(np.any(result != 0), f"{name}: output is all zeros")


class TestCoreEffects(unittest.TestCase, _EffectTestBase):
    """Test core/effects/ module functions directly."""

    @classmethod
    def setUpClass(cls):
        cls.sr = 44100
        cls.signal = _make_test_signal(cls.sr, 0.5, 2)
        cls.noise = _make_noise(cls.sr, 0.5, 2)
        cls.n = len(cls.signal)

    def test_reverse(self):
        from core.effects.reverse import reverse
        r = reverse(self.signal, 0, self.n)
        self.assert_valid_output(r, self.signal, "reverse")

    def test_volume(self):
        from core.effects.volume import volume
        r = volume(self.signal, 0, self.n, gain_pct=50.0)
        self.assert_valid_output(r, self.signal, "volume")
        self.assertLess(np.max(np.abs(r)), np.max(np.abs(self.signal)) + 0.01)

    def test_saturation_soft(self):
        from core.effects.saturation import saturate
        r = saturate(self.signal, 0, self.n, mode="soft", drive=5.0)
        self.assert_valid_output(r, self.signal, "saturation_soft")

    def test_saturation_hard(self):
        from core.effects.saturation import saturate
        r = saturate(self.signal, 0, self.n, mode="hard", drive=5.0)
        self.assert_valid_output(r, self.signal, "saturation_hard")

    def test_saturation_overdrive(self):
        from core.effects.saturation import saturate
        r = saturate(self.signal, 0, self.n, mode="overdrive", drive=5.0, tone=0.5)
        self.assert_valid_output(r, self.signal, "saturation_overdrive")

    def test_saturation_backward_compat(self):
        """Verify old function aliases still work."""
        from core.effects.saturation import hard_clip, soft_clip, overdrive
        r1 = hard_clip(self.signal, 0, self.n, threshold=0.5)
        r2 = soft_clip(self.signal, 0, self.n, drive=3.0)
        r3 = overdrive(self.signal, 0, self.n, gain=5.0, tone=0.5)
        for r, name in [(r1, "hard_clip"), (r2, "soft_clip"), (r3, "overdrive")]:
            self.assert_valid_output(r, self.signal, name)

    def test_bitcrusher(self):
        from core.effects.bitcrusher import bitcrush
        r = bitcrush(self.signal, 0, self.n, bit_depth=8, downsample=4)
        self.assert_valid_output(r, self.signal, "bitcrusher")

    def test_delay(self):
        from core.effects.delay import delay
        r = delay(self.signal, 0, self.n, sr=self.sr, delay_ms=200, feedback=0.4, mix=0.5)
        self.assert_valid_output(r, self.signal, "delay", allow_length_change=True)
        # v4.2: delay should be >= original length (tail extension)
        self.assertGreaterEqual(len(r), self.n, "delay: should extend or match original")

    def test_chorus(self):
        from core.effects.chorus import chorus
        r = chorus(self.signal, 0, self.n, sr=self.sr, depth_ms=5.0, rate_hz=1.0, mix=0.5)
        self.assert_valid_output(r, self.signal, "chorus")

    def test_tremolo(self):
        from core.effects.tremolo import tremolo
        r = tremolo(self.signal, 0, self.n, sr=self.sr, rate_hz=5.0, depth=0.8)
        self.assert_valid_output(r, self.signal, "tremolo")

    def test_phaser(self):
        from core.effects.phaser import phaser
        r = phaser(self.signal, 0, self.n, sr=self.sr, rate_hz=0.5, depth=0.7)
        self.assert_valid_output(r, self.signal, "phaser")

    def test_distortion(self):
        from core.effects.distortion import distortion
        r = distortion(self.signal, 0, self.n, drive=5.0, tone=0.5)
        self.assert_valid_output(r, self.signal, "distortion")

    def test_filter(self):
        from core.effects.filter import resonant_filter
        r = resonant_filter(self.signal, 0, self.n, sr=self.sr,
                            cutoff=1000.0, resonance=1.0, filter_type="lowpass")
        self.assert_valid_output(r, self.signal, "filter")

    def test_pan(self):
        from core.effects.pan import pan_stereo
        r = pan_stereo(self.signal, 0, self.n, pan=0.8)
        self.assert_valid_output(r, self.signal, "pan")

    def test_ring_mod(self):
        from core.effects.ring_mod import ring_mod
        r = ring_mod(self.signal, 0, self.n, sr=self.sr, freq=200.0, mix=0.7)
        self.assert_valid_output(r, self.signal, "ring_mod")

    def test_stutter(self):
        from core.effects.stutter import stutter
        r = stutter(self.signal, 0, self.n, repeats=4, decay=0.8)
        self.assert_valid_output(r, self.signal, "stutter", allow_length_change=True)

    def test_shuffle(self):
        from core.effects.shuffle import shuffle
        r = shuffle(self.signal, 0, self.n, slices=8)
        self.assert_valid_output(r, self.signal, "shuffle")

    def test_vinyl(self):
        from core.effects.vinyl import vinyl
        r = vinyl(self.signal, 0, self.n, sr=self.sr, noise=0.3, crackle=0.5)
        self.assert_valid_output(r, self.signal, "vinyl")

    def test_tape_stop(self):
        from core.effects.tape_stop import tape_stop
        r = tape_stop(self.signal, 0, self.n, sr=self.sr, duration_pct=0.5)
        self.assert_valid_output(r, self.signal, "tape_stop", allow_length_change=True)

    def test_buffer_freeze(self):
        from core.effects.buffer_freeze import buffer_freeze
        r = buffer_freeze(self.signal, 0, self.n, sr=self.sr, grain_ms=50)
        self.assert_valid_output(r, self.signal, "buffer_freeze")

    def test_datamosh(self):
        from core.effects.datamosh import datamosh
        r = datamosh(self.signal, 0, self.n, intensity=0.5)
        self.assert_valid_output(r, self.signal, "datamosh")

    def test_granular(self):
        from core.effects.granular import granular
        r = granular(self.signal, 0, self.n, sr=self.sr, grain_size_ms=50, density=1.0)
        self.assert_valid_output(r, self.signal, "granular", allow_length_change=True)

    def test_time_stretch(self):
        from core.effects.time_stretch import time_stretch
        r = time_stretch(self.signal, 0, self.n, factor=1.5)
        self.assert_valid_output(r, self.signal, "time_stretch", allow_length_change=True)

    def test_pitch_shift(self):
        from core.effects.pitch_shift import pitch_shift
        r = pitch_shift(self.signal, 0, self.n, sr=self.sr, semitones=3)
        self.assert_valid_output(r, self.signal, "pitch_shift", allow_length_change=True)

    def test_ott(self):
        from core.effects.ott import ott
        r = ott(self.signal, 0, self.n, sr=self.sr, depth=0.5)
        self.assert_valid_output(r, self.signal, "ott")


@unittest.skipUnless(HAS_QT, "PyQt6 not available — skipping plugin tests")
class TestPluginProcess(unittest.TestCase, _EffectTestBase):
    """Test effect plugins via their process() function (like the app does)."""

    @classmethod
    def setUpClass(cls):
        cls.sr = 44100
        cls.signal = _make_test_signal(cls.sr, 0.5, 2)
        cls.n = len(cls.signal)

    def _run_plugin(self, module_path, name, **extra_kw):
        """Import and run a plugin's process() function."""
        import importlib
        mod = importlib.import_module(module_path)
        result = mod.process(self.signal.copy(), 0, self.n, sr=self.sr, **extra_kw)
        self.assert_valid_output(result, self.signal, name, allow_length_change=True)
        return result

    def test_plugin_reverse(self):
        self._run_plugin("effects.effect_reverse", "plugin:reverse")

    def test_plugin_volume(self):
        self._run_plugin("effects.effect_volume", "plugin:volume", gain_pct=80.0)

    def test_plugin_saturation(self):
        for mode in ["soft", "hard", "overdrive"]:
            self._run_plugin("effects.effect_saturation", f"plugin:sat_{mode}",
                             type=mode, drive=5.0)

    def test_plugin_bitcrusher(self):
        self._run_plugin("effects.effect_bitcrusher", "plugin:bitcrusher",
                         bit_depth=8, downsample=4)

    def test_plugin_delay(self):
        self._run_plugin("effects.effect_delay", "plugin:delay",
                         delay_ms=200, feedback=0.4, mix=0.5)

    def test_plugin_chorus(self):
        self._run_plugin("effects.effect_chorus", "plugin:chorus",
                         depth_ms=5.0, rate_hz=1.0, mix=0.5)

    def test_plugin_tremolo(self):
        self._run_plugin("effects.effect_tremolo", "plugin:tremolo",
                         rate_hz=5.0, depth=0.8)

    def test_plugin_phaser(self):
        self._run_plugin("effects.effect_phaser", "plugin:phaser",
                         rate_hz=0.5, depth=0.7)

    def test_plugin_distortion(self):
        self._run_plugin("effects.effect_distortion", "plugin:distortion",
                         drive=5.0, tone=0.5)

    def test_plugin_filter(self):
        self._run_plugin("effects.effect_filter", "plugin:filter",
                         cutoff=1000.0, resonance=1.0, filter_type="lowpass")

    def test_plugin_pan(self):
        self._run_plugin("effects.effect_pan", "plugin:pan", pan=0.8)

    def test_plugin_ring_mod(self):
        self._run_plugin("effects.effect_ring_mod", "plugin:ring_mod",
                         freq=200.0, mix=0.7)

    def test_plugin_stutter(self):
        self._run_plugin("effects.effect_stutter", "plugin:stutter",
                         repeats=4, decay=0.8)

    def test_plugin_shuffle(self):
        self._run_plugin("effects.effect_shuffle", "plugin:shuffle", slices=8)

    def test_plugin_vinyl(self):
        self._run_plugin("effects.effect_vinyl", "plugin:vinyl",
                         noise=0.3, crackle=0.5)

    def test_plugin_tape_stop(self):
        self._run_plugin("effects.effect_tape_stop", "plugin:tape_stop", duration_pct=0.5)

    def test_plugin_buffer_freeze(self):
        self._run_plugin("effects.effect_buffer_freeze", "plugin:buffer_freeze",
                         grain_ms=50)

    def test_plugin_datamosh(self):
        self._run_plugin("effects.effect_datamosh", "plugin:datamosh",
                         intensity=0.5)

    def test_plugin_granular(self):
        self._run_plugin("effects.effect_granular", "plugin:granular",
                         grain_size_ms=50, density=1.0)

    def test_plugin_ott(self):
        self._run_plugin("effects.effect_ott", "plugin:ott", depth=0.5)

    def test_plugin_pitch_shift(self):
        self._run_plugin("effects.effect_pitch_shift", "plugin:pitch_shift",
                         semitones=3)

    def test_plugin_time_stretch(self):
        self._run_plugin("effects.effect_time_stretch", "plugin:time_stretch",
                         factor=1.5)


class TestEdgeCases(unittest.TestCase, _EffectTestBase):
    """Test effects with edge-case inputs."""

    @classmethod
    def setUpClass(cls):
        cls.sr = 44100

    def test_silence_input(self):
        """Effects should handle silence without errors."""
        silence = np.zeros((22050, 2), dtype=np.float32)
        from core.effects.reverse import reverse
        from core.effects.delay import delay
        from core.effects.chorus import chorus
        r1 = reverse(silence, 0, len(silence))
        r2 = delay(silence, 0, len(silence), sr=self.sr, delay_ms=100)
        r3 = chorus(silence, 0, len(silence), sr=self.sr)
        for r, name in [(r1, "reverse"), (r2, "delay"), (r3, "chorus")]:
            self.assertIsNotNone(r, f"{name} on silence returned None")
            self.assertFalse(np.any(np.isnan(r)), f"{name} on silence has NaN")

    def test_very_short_input(self):
        """Effects should handle very short audio (<100 samples)."""
        short = np.random.randn(64, 2).astype(np.float32) * 0.5
        from core.effects.tremolo import tremolo
        from core.effects.bitcrusher import bitcrush
        r1 = tremolo(short, 0, len(short), sr=self.sr, rate_hz=5.0, depth=0.5)
        r2 = bitcrush(short, 0, len(short), bit_depth=8, downsample=2)
        for r, name in [(r1, "tremolo_short"), (r2, "bitcrush_short")]:
            self.assertIsNotNone(r, f"{name} returned None")
            self.assertFalse(np.any(np.isnan(r)), f"{name} has NaN")

    def test_mono_input(self):
        """Effects should handle mono input."""
        mono = (0.5 * np.sin(np.linspace(0, 10, 22050))).astype(np.float32)
        from core.effects.volume import volume
        from core.effects.saturation import saturate
        r1 = volume(mono, 0, len(mono), gain_pct=80.0)
        r2 = saturate(mono, 0, len(mono), mode="soft", drive=3.0)
        for r, name in [(r1, "volume_mono"), (r2, "sat_mono")]:
            self.assertIsNotNone(r, f"{name} returned None")
            self.assertFalse(np.any(np.isnan(r)), f"{name} has NaN")

    def test_loud_input(self):
        """Effects should handle clipping input (values > 1.0)."""
        loud = _make_test_signal(self.sr, 0.3, 2) * 3.0
        from core.effects.saturation import saturate
        from core.effects.distortion import distortion
        r1 = saturate(loud, 0, len(loud), mode="hard", drive=2.0)
        r2 = distortion(loud, 0, len(loud), drive=2.0)
        for r, name in [(r1, "sat_loud"), (r2, "dist_loud")]:
            self.assert_valid_output(r, loud, name, max_amplitude=1.5)


class TestUtils(unittest.TestCase):
    """Test core/effects/utils.py helper functions."""

    def test_fade_in(self):
        from core.effects.utils import fade_in
        audio = np.ones((1000, 2), dtype=np.float32)
        r = fade_in(audio, 200)
        self.assertAlmostEqual(r[0, 0], 0.0, places=3)
        self.assertAlmostEqual(r[500, 0], 1.0, places=3)

    def test_fade_out(self):
        from core.effects.utils import fade_out
        audio = np.ones((1000, 2), dtype=np.float32)
        r = fade_out(audio, 200)
        self.assertAlmostEqual(r[-1, 0], 0.0, places=3)
        self.assertAlmostEqual(r[0, 0], 1.0, places=3)

    def test_normalize(self):
        from core.effects.utils import normalize
        audio = np.ones((1000, 2), dtype=np.float32) * 0.1
        r = normalize(audio, target_peak=0.95)
        self.assertAlmostEqual(np.max(np.abs(r)), 0.95, places=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)


