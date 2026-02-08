"""Configuration & constants for Glitch Maker."""
import os, json

APP_NAME = "Glitch Maker"
APP_VERSION = "3.10"
WINDOW_MIN_WIDTH = 1050
WINDOW_MIN_HEIGHT = 650
RECORDING_SAMPLE_RATE = 44100
RECORDING_CHANNELS = 2

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aiff", ".aac"}
ALL_EXTENSIONS = AUDIO_EXTENSIONS | {".gspi"}

COLORS = {
    "bg_dark":           "#0d0d1a",
    "bg_medium":         "#151528",
    "bg_panel":          "#1a1a30",
    "bg_light":          "#222244",
    "accent":            "#6c5ce7",
    "accent_hover":      "#7c6cf7",
    "accent_secondary":  "#533483",
    "border":            "#2a2a4a",
    "text":              "#e0e0e8",
    "text_dim":          "#8888aa",
    "button_bg":         "#252545",
    "button_hover":      "#303060",
    "scrollbar":         "#3a3a5a",
    "playhead":          "#00d4aa",
    "selection":         "#e94560",
    "recording":         "#e94560",
    "clip_highlight":    "#16c79a",
}

_SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".glitchmaker_settings.json")

def load_settings() -> dict:
    """Charge les settings depuis settings.json."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(s: dict):
    """Sauvegarde les settings dans settings.json."""
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass
