"""
User plugin loader — discovers & loads user-imported effect plugins.

Each user plugin is a .py file in plugins/user_plugins/ that defines:
  METADATA = {"id": str, "name": str, "icon": str, "color": str, "section": str}
  PARAMS   = [{"key": str, "label": str, "type": "int"|"float"|"choice"|"bool", ...}, ...]
  def process(audio_data, start, end, sr=44100, **kw) -> audio_data

Optional: a .json file with same stem for translations:
  {"en": {"name": "...", "short": "..."}, "fr": {"name": "...", "short": "..."}}
"""
from utils.logger import get_logger
_log = get_logger("user_loader")

import os
import sys
import json
import importlib.util
import traceback

# Resolve user plugins directory (works both normal and frozen)
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.join(os.path.dirname(sys.executable), "plugins", "user_plugins")
else:
    _BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_plugins")

_REGISTRY_PATH = os.path.join(_BASE_DIR, "_registry.json")

# ═══ Translation overlay ═══

_user_translations: dict = {}  # {plugin_id: {lang: {key: val}}}


def get_user_translation(plugin_id: str, key: str, lang: str) -> str | None:
    """Get a user plugin translation string, or None if not found."""
    pd = _user_translations.get(plugin_id)
    if pd:
        ld = pd.get(lang, pd.get("en"))
        if ld:
            return ld.get(key)
    return None


# ═══ Registry management ═══

def _ensure_dir():
    """Cree le dossier user_plugins s il n existe pas."""
    os.makedirs(_BASE_DIR, exist_ok=True)


def _load_registry() -> list:
    """Charge le registre des plugins utilisateur (JSON)."""
    if os.path.isfile(_REGISTRY_PATH):
        try:
            with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as _ex:
            _log.debug("Non-critical: %s", _ex)
    return []


def _save_registry(entries: list):
    """Sauvegarde le registre des plugins utilisateur."""
    _ensure_dir()
    with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def get_user_plugins_dir() -> str:
    """Retourne le chemin du dossier user_plugins."""
    _ensure_dir()
    return _BASE_DIR


def list_installed() -> list:
    """Return list of installed user plugin entries."""
    return _load_registry()


def install_plugin(py_path: str, json_path: str | None = None) -> dict:
    """
    Install a user plugin by copying .py (and optional .json) to user_plugins/.
    Returns the registry entry dict, or raises ValueError on error.
    """
    import shutil
    _ensure_dir()

    # Load and validate the module
    spec = importlib.util.spec_from_file_location("_temp_plugin", py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    meta = getattr(mod, "METADATA", None)
    if not meta or not isinstance(meta, dict):
        raise ValueError("Plugin .py must define METADATA dict")
    for k in ("id", "name", "icon", "color", "section"):
        if k not in meta:
            raise ValueError(f"METADATA missing required key: '{k}'")
    if not hasattr(mod, "process") or not callable(mod.process):
        raise ValueError("Plugin .py must define process(audio_data, start, end, sr, **kw)")

    pid = meta["id"]
    stem = pid.replace(" ", "_").lower()

    # Copy .py
    dst_py = os.path.join(_BASE_DIR, f"{stem}.py")
    shutil.copy2(py_path, dst_py)

    # Copy .json (translations) if provided
    dst_json = None
    if json_path and os.path.isfile(json_path):
        dst_json = os.path.join(_BASE_DIR, f"{stem}.json")
        shutil.copy2(json_path, dst_json)

    # Update registry
    registry = _load_registry()
    # Remove existing entry with same id
    registry = [e for e in registry if e.get("id") != pid]
    entry = {
        "id": pid,
        "file": f"{stem}.py",
        "lang_file": f"{stem}.json" if dst_json else None,
        "name": meta["name"],
        "icon": meta["icon"],
        "color": meta["color"],
        "section": meta["section"],
    }
    registry.append(entry)
    _save_registry(registry)

    return entry


def uninstall_plugin(plugin_id: str):
    """Remove a user plugin by id."""
    registry = _load_registry()
    entry = None
    for e in registry:
        if e.get("id") == plugin_id:
            entry = e
            break
    if not entry:
        return

    # Remove files
    py_file = os.path.join(_BASE_DIR, entry.get("file", ""))
    if os.path.isfile(py_file):
        os.remove(py_file)
    json_file = entry.get("lang_file")
    if json_file:
        jp = os.path.join(_BASE_DIR, json_file)
        if os.path.isfile(jp):
            os.remove(jp)

    # Update registry
    registry = [e for e in registry if e.get("id") != plugin_id]
    _save_registry(registry)
    _user_translations.pop(plugin_id, None)


# ═══ Dynamic dialog generation from PARAMS ═══

def _make_dialog_class(meta: dict, params: list):
    """Generate a QDialog subclass from PARAMS definition."""
    from gui.effect_dialogs import _Base, _slider_int, _slider_float
    from PyQt6.QtWidgets import QComboBox, QCheckBox

    class UserPluginDialog(_Base):
        def __init__(self, parent=None):
            super().__init__(meta.get("name", "Effect"), parent)
            self._widgets = {}
            for p in params:
                key = p["key"]
                label = p.get("label", key)
                ptype = p.get("type", "float")

                if ptype == "int":
                    w = _slider_int(self._lo, label,
                                    p.get("min", 0), p.get("max", 100),
                                    p.get("default", 50),
                                    p.get("suffix", ""))
                    self._widgets[key] = ("int", w)

                elif ptype == "float":
                    w = _slider_float(self._lo, label,
                                      p.get("min", 0.0), p.get("max", 1.0),
                                      p.get("default", 0.5),
                                      p.get("step", 0.01),
                                      p.get("decimals", 2),
                                      p.get("suffix", ""),
                                      p.get("mult", 100))
                    self._widgets[key] = ("float", w)

                elif ptype == "choice":
                    from PyQt6.QtWidgets import QLabel
                    self._lo.addWidget(QLabel(label))
                    cb = QComboBox()
                    cb.addItems(p.get("options", []))
                    default = p.get("default", "")
                    idx = cb.findText(default)
                    if idx >= 0:
                        cb.setCurrentIndex(idx)
                    self._lo.addWidget(cb)
                    self._widgets[key] = ("choice", cb)

                elif ptype == "bool":
                    cb = QCheckBox(label)
                    cb.setChecked(p.get("default", False))
                    self._lo.addWidget(cb)
                    self._widgets[key] = ("bool", cb)

            if not params:
                from PyQt6.QtWidgets import QLabel
                self._lo.addWidget(QLabel("No parameters."))

            self._finish()

        def get_params(self):
            """Retourne les parametres d un plugin utilisateur."""
            result = {}
            for key, (ptype, w) in self._widgets.items():
                if ptype in ("int", "float"):
                    result[key] = w.value()
                elif ptype == "choice":
                    result[key] = w.currentText()
                elif ptype == "bool":
                    result[key] = w.isChecked()
            return result

        def set_params(self, p):
            """Met a jour les parametres d un plugin utilisateur."""
            for key, (ptype, w) in self._widgets.items():
                if key in p:
                    if ptype in ("int", "float"):
                        w.setValue(p[key])
                    elif ptype == "choice":
                        idx = w.findText(str(p[key]))
                        if idx >= 0:
                            w.setCurrentIndex(idx)
                    elif ptype == "bool":
                        w.setChecked(bool(p[key]))

    return UserPluginDialog


# ═══ Load all user plugins ═══

def load_user_plugins() -> dict:
    """Load all installed user plugins. Returns {id: Plugin}."""
    from plugins.loader import Plugin

    registry = _load_registry()
    plugins = {}

    for entry in registry:
        pid = entry.get("id")
        py_file = entry.get("file")
        if not pid or not py_file:
            continue

        py_path = os.path.join(_BASE_DIR, py_file)
        if not os.path.isfile(py_path):
            continue

        try:
            # Load module
            spec = importlib.util.spec_from_file_location(f"user_plugin_{pid}", py_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            meta = getattr(mod, "METADATA", {})
            params = getattr(mod, "PARAMS", [])
            process_fn = getattr(mod, "process", None)
            if not process_fn:
                continue

            # Load translations
            lang_file = entry.get("lang_file")
            if lang_file:
                jp = os.path.join(_BASE_DIR, lang_file)
                if os.path.isfile(jp):
                    try:
                        with open(jp, "r", encoding="utf-8") as f:
                            _user_translations[pid] = json.load(f)
                    except Exception as _ex:
                        _log.debug("Non-critical: %s", _ex)

            # Create wrapper function
            def _make_wrapper(fn):
                """Cree une fonction wrapper pour un plugin utilisateur."""
                def wrapper(audio_data, start, end, sr=44100, **kw):
                    """Fonction wrapper qui appelle process() du plugin utilisateur."""
                    return fn(audio_data, start, end, sr=sr, **kw)
                return wrapper

            # Generate dialog class
            dialog_cls = _make_dialog_class(meta, params)

            # Create Plugin
            plugin = Plugin(
                eid=pid,
                icon=meta.get("icon", "?"),
                color=meta.get("color", "#888888"),
                section=meta.get("section", "Custom"),
                name_key=f"_user_.{pid}",  # special prefix for user plugins
                dialog_class=dialog_cls,
                process_fn=_make_wrapper(process_fn),
            )
            plugins[pid] = plugin

        except Exception as ex:
            _log.error("Failed to load '%s': %s", pid, ex)
            traceback.print_exc()

    return plugins
