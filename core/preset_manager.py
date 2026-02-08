"""Preset manager — built-in + user presets, tag management with cascade delete."""
import json, os, sys

if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS
else:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    _BASE_DIR = os.path.dirname(_THIS_DIR)

_BUILTIN_PATH = os.path.join(_BASE_DIR, "assets", "presets.json")
_USER_PATH = os.path.join(os.path.expanduser("~"), ".glitchmaker_presets.json")
_USER_TAGS_PATH = os.path.join(os.path.expanduser("~"), ".glitchmaker_tags.json")
_DELETED_TAGS_PATH = os.path.join(os.path.expanduser("~"), ".glitchmaker_deleted_tags.json")


class PresetManager:
    def __init__(self):
        self._builtin: list[dict] = []
        self._user: list[dict] = []
        self._builtin_tags: list[str] = []
        self._user_tags: list[str] = []
        self._deleted_tags: list[str] = []  # tracks deleted builtin tags
        self._load()

    def _load(self):
        # Built-in presets & tags
        """Charge les presets depuis les fichiers JSON (builtin + user)."""
        try:
            with open(_BUILTIN_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._builtin = data.get("presets", [])
            self._builtin_tags = data.get("tags", [])
        except Exception:
            self._builtin, self._builtin_tags = [], []

        # User presets
        try:
            with open(_USER_PATH, "r", encoding="utf-8") as f:
                self._user = json.load(f)
        except Exception:
            self._user = []

        # User-added tags
        try:
            with open(_USER_TAGS_PATH, "r", encoding="utf-8") as f:
                self._user_tags = json.load(f)
        except Exception:
            self._user_tags = []

        # Deleted tags (including builtin ones user removed)
        try:
            with open(_DELETED_TAGS_PATH, "r", encoding="utf-8") as f:
                self._deleted_tags = json.load(f)
        except Exception:
            self._deleted_tags = []

    def _save_user(self):
        """Sauvegarde les presets utilisateur dans user_presets.json."""
        try:
            with open(_USER_PATH, "w", encoding="utf-8") as f:
                json.dump(self._user, f, indent=2)
        except Exception:
            pass

    def _save_tags(self):
        """Sauvegarde les associations tags/presets."""
        try:
            with open(_USER_TAGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._user_tags, f, indent=2)
        except Exception:
            pass

    def _save_deleted_tags(self):
        """Sauvegarde les presets builtin supprimes."""
        try:
            with open(_DELETED_TAGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._deleted_tags, f, indent=2)
        except Exception:
            pass

    # ── Presets ──

    def get_all_presets(self) -> list[dict]:
        """Retourne tous les presets (builtin + user) non supprimes."""
        return self._builtin + self._user

    def get_preset(self, name: str) -> dict | None:
        """Retourne un preset par son nom."""
        for p in self.get_all_presets():
            if p["name"] == name:
                return p
        return None

    def get_presets_by_tag(self, tag: str) -> list[dict]:
        """Retourne les presets qui ont le tag donne."""
        return [p for p in self.get_all_presets() if tag in p.get("tags", [])]

    def add_preset(self, name: str, description: str, tags: list[str], effects: list[dict]):
        """Ajoute un nouveau preset utilisateur."""
        self._user.append({
            "name": name, "description": description,
            "tags": tags, "effects": effects, "builtin": False,
        })
        self._save_user()

    def delete_preset(self, name: str) -> bool:
        """Supprime un preset (utilisateur ou masque un builtin)."""
        for i, p in enumerate(self._user):
            if p["name"] == name:
                self._user.pop(i)
                self._save_user()
                return True
        return False

    # ── Tags ──

    def get_all_tags(self) -> list[str]:
        """Get all active tags (builtin + user, minus deleted ones)."""
        tags = set()
        for t in self._builtin_tags:
            if t not in self._deleted_tags:
                tags.add(t)
        for t in self._user_tags:
            tags.add(t)
        # Also include tags from presets that aren't in deleted list
        for p in self.get_all_presets():
            for t in p.get("tags", []):
                if t not in self._deleted_tags:
                    tags.add(t)
        return sorted(tags)

    def add_tag(self, tag: str):
        """Add a new tag. If it was previously deleted, un-delete it."""
        if not tag:
            return
        if tag in self._deleted_tags:
            self._deleted_tags.remove(tag)
            self._save_deleted_tags()
        if tag not in self._builtin_tags and tag not in self._user_tags:
            self._user_tags.append(tag)
            self._save_tags()

    def delete_tag(self, tag: str) -> bool:
        """Delete a tag. Removes it from ALL presets (builtin runtime + user persisted)."""
        # Remove from user tags list
        if tag in self._user_tags:
            self._user_tags.remove(tag)
            self._save_tags()

        # Track as deleted (so builtin tags stay hidden)
        if tag not in self._deleted_tags:
            self._deleted_tags.append(tag)
            self._save_deleted_tags()

        # Remove from builtin presets (runtime only, doesn't modify assets/presets.json)
        for p in self._builtin:
            if tag in p.get("tags", []):
                p["tags"].remove(tag)

        # Remove from user presets (persisted)
        changed = False
        for p in self._user:
            if tag in p.get("tags", []):
                p["tags"].remove(tag)
                changed = True
        if changed:
            self._save_user()

        return True

    def is_builtin_tag(self, tag: str) -> bool:
        """Retourne True si le tag est un tag builtin."""
        return tag in self._builtin_tags and tag not in self._deleted_tags

    # ── Export / Import (.pspi) ──

    def export_presets(self, filepath: str, preset_names: list[str] | None = None):
        """Export presets to .pspi file. If names is None, export all user presets."""
        all_p = self.get_all_presets()
        if preset_names:
            presets = [p for p in all_p if p["name"] in preset_names]
        else:
            presets = list(self._user) if self._user else all_p

        # Collect tags used by exported presets
        tags = sorted({t for p in presets for t in p.get("tags", [])})

        data = {
            "format": "glitchmaker_presets",
            "version": 1,
            "tags": tags,
            "presets": presets,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def import_presets(self, filepath: str) -> tuple[int, list[str]]:
        """Import presets from .pspi file. Returns (count_imported, skipped_names)."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("format") != "glitchmaker_presets":
            raise ValueError("Invalid preset file format")

        imported = 0
        skipped = []
        existing = {p["name"] for p in self.get_all_presets()}

        # Import tags
        for tag in data.get("tags", []):
            if tag and tag not in self.get_all_tags():
                self.add_tag(tag)

        # Import presets
        for p in data.get("presets", []):
            name = p.get("name", "")
            if not name:
                continue
            if name in existing:
                skipped.append(name)
                continue
            self._user.append({
                "name": name,
                "description": p.get("description", ""),
                "tags": p.get("tags", []),
                "effects": p.get("effects", []),
                "builtin": False,
            })
            existing.add(name)
            imported += 1

        if imported > 0:
            self._save_user()

        return imported, skipped
