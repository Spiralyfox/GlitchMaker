"""Configuration & constants for Glitch Maker."""
import os, json

APP_NAME = "Glitch Maker"
APP_VERSION = "6.2"
WINDOW_MIN_WIDTH = 1050
WINDOW_MIN_HEIGHT = 650
RECORDING_SAMPLE_RATE = 44100
RECORDING_CHANNELS = 2

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aiff", ".aac"}
ALL_EXTENSIONS = AUDIO_EXTENSIONS | {".gspi"}

# ── Dark theme (default) ──
COLORS_DARK = {
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

# ── Light theme ──
COLORS_LIGHT = {
    "bg_dark":           "#f0f0f5",
    "bg_medium":         "#e4e4ec",
    "bg_panel":          "#eaeaf2",
    "bg_light":          "#ffffff",
    "accent":            "#6c5ce7",
    "accent_hover":      "#7c6cf7",
    "accent_secondary":  "#8b7cf0",
    "border":            "#c8c8d8",
    "text":              "#1a1a2e",
    "text_dim":          "#666680",
    "button_bg":         "#d8d8e8",
    "button_hover":      "#c0c0d8",
    "scrollbar":         "#b0b0c8",
    "playhead":          "#00b894",
    "selection":         "#e94560",
    "recording":         "#e94560",
    "clip_highlight":    "#16c79a",
}

# ── Preset tag colors (centralized, step 46) ──
TAG_COLORS = {
    "Autotune": "#f72585", "Hyperpop": "#ff006e", "Digicore": "#7209b7",
    "Emocore": "#e94560", "Glitch": "#9b2226", "Vocal": "#4cc9f0",
    "Ambient": "#2a9d8f", "Lo-fi": "#606c38", "Aggressive": "#bb3e03",
    "Experimental": "#b5179e", "Electro": "#0ea5e9", "Tape": "#6b705c",
    "Clean": "#16c79a", "Subtle": "#457b9d", "Dariacore": "#c74b50",
    "Rhythmic": "#e07c24", "Psychedelic": "#6d597a", "Bass": "#264653",
    "Cinematic": "#3d5a80",
}

# ── UI accent colors ──
FAVORITE_STAR = "#ffd93d"

# Active color dict — starts as dark, updated by set_theme()
COLORS = dict(COLORS_DARK)

_current_theme = "dark"

def get_theme() -> str:
    """Return current theme name ('dark' or 'light')."""
    return _current_theme

def set_theme(theme: str):
    """Switch between 'dark' and 'light' theme."""
    global _current_theme
    _current_theme = theme
    src = COLORS_LIGHT if theme == "light" else COLORS_DARK
    COLORS.clear()
    COLORS.update(src)

def get_colors() -> dict:
    """Return the current color palette dict."""
    return COLORS

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
