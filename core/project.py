"""
Project file management — .gspi format (ZIP with WAV + JSON + undo state).
v4.4 — Stores base_audio, effect_ops, undo/redo stacks.
"""
import os, json, tempfile, zipfile, copy
import numpy as np
import soundfile as sf
from core.timeline import Timeline, AudioClip


def save_project(filepath, timeline, sr, source_path="",
                 base_audio=None, effect_ops=None,
                 undo_stack=None, redo_stack=None):
    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "version": "5.6",
            "sample_rate": sr,
            "source_path": source_path,
            "clips": [],
            "effect_ops": _ser_ops(effect_ops or []),
        }

        for i, clip in enumerate(timeline.clips):
            wav_name = f"clip_{i:03d}.wav"
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            try:
                sf.write(tmp.name, clip.audio_data, clip.sample_rate, subtype="PCM_16")
                zf.write(tmp.name, wav_name)
            finally:
                os.unlink(tmp.name)
            meta["clips"].append({
                "name": clip.name, "file": wav_name,
                "position": clip.position, "color": clip.color,
            })

        if base_audio is not None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            try:
                sf.write(tmp.name, base_audio, sr, subtype="PCM_16")
                zf.write(tmp.name, "base_audio.wav")
                meta["has_base_audio"] = True
            finally:
                os.unlink(tmp.name)

        # Save undo/redo as ops-only (no audio snapshots for size)
        if undo_stack:
            meta["undo_stack"] = [
                {"desc": s.get("desc",""), "ops": _ser_ops(s.get("ops",[]))}
                for s in undo_stack if "ops" in s
            ]
        if redo_stack:
            meta["redo_stack"] = [
                {"desc": s.get("desc",""), "ops": _ser_ops(s.get("ops",[]))}
                for s in redo_stack if "ops" in s
            ]

        zf.writestr("project.json", json.dumps(meta, indent=2))


def load_project(filepath):
    result = {"timeline": Timeline(), "sr": 44100, "source": "",
              "base_audio": None, "effect_ops": [], "undo_stack": [], "redo_stack": []}

    with zipfile.ZipFile(filepath, 'r') as zf:
        meta = json.loads(zf.read("project.json"))
        sr = meta.get("sample_rate", 44100)
        result["sr"] = sr
        result["source"] = meta.get("source_path", "")
        tl = result["timeline"]
        tl.sample_rate = sr

        colors = ["#533483", "#e94560", "#0f3460", "#16c79a", "#ff6b35", "#c74b50"]
        for i, cm in enumerate(meta.get("clips", [])):
            wav_data = zf.read(cm["file"])
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(wav_data); tmp.close()
            try:
                data, clip_sr = sf.read(tmp.name, dtype="float32", always_2d=True)
            finally:
                os.unlink(tmp.name)
            clip = AudioClip(
                name=cm.get("name", f"Clip {i+1}"),
                audio_data=data, sample_rate=clip_sr,
                position=cm.get("position", 0),
                color=cm.get("color", colors[i % len(colors)]))
            tl.clips.append(clip)

        if meta.get("has_base_audio") and "base_audio.wav" in zf.namelist():
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(zf.read("base_audio.wav")); tmp.close()
            try:
                data, _ = sf.read(tmp.name, dtype="float32", always_2d=True)
                result["base_audio"] = data
            finally:
                os.unlink(tmp.name)

        result["effect_ops"] = _deser_ops(meta.get("effect_ops", []))

        # Restore undo/redo (ops only — audio will be re-rendered)
        for s in meta.get("undo_stack", []):
            result["undo_stack"].append({
                "desc": s.get("desc",""),
                "ops": _deser_ops(s.get("ops", []))
            })
        for s in meta.get("redo_stack", []):
            result["redo_stack"].append({
                "desc": s.get("desc",""),
                "ops": _deser_ops(s.get("ops", []))
            })

    return result


def _ser_ops(ops):
    out = []
    for op in ops:
        d = {k: v for k, v in op.items() if k not in ("_process_fn", "_state_after")}
        # Convert numpy types
        for key in ["start", "end"]:
            if key in d and hasattr(d[key], 'item'):
                d[key] = int(d[key])
        out.append(d)
    return out

def _deser_ops(data):
    return [dict(d) for d in data]
