"""Persistent settings, presets and session history (JSON files).

Both stores are Kivy EventDispatchers, so the UI binds to their properties
directly and every change is saved automatically.
"""

import json
import os
from datetime import datetime, timedelta

from kivy.event import EventDispatcher
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    OptionProperty,
)

from .device import LED_LEVELS, MAX_LEVEL, MIN_LEVEL, STIM_SIDES

MIN_MINUTES = 1
MAX_MINUTES = 60

DEFAULT_PRESETS = [
    {"name": "Quick reset", "minutes": 4, "intensity": 5},
    {"name": "Stress", "minutes": 10, "intensity": 5},
    {"name": "Sleep", "minutes": 20, "intensity": 3},
]


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        print(f"Could not read {path}: {e}")
        return None


def _write_json(path, data):
    """Write atomically so a crash mid-write never corrupts the file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        print(f"Could not save {path}: {e}")


def _clean_preset(p):
    try:
        name = str(p["name"]).strip()[:40]
        minutes = max(MIN_MINUTES, min(MAX_MINUTES, int(p["minutes"])))
        intensity = max(MIN_LEVEL, min(MAX_LEVEL, int(p["intensity"])))
    except (KeyError, TypeError, ValueError):
        return None
    return {"name": name, "minutes": minutes, "intensity": intensity} if name else None


class Settings(EventDispatcher):
    stim_side = OptionProperty("D", options=list(STIM_SIDES))
    led_intensity = OptionProperty("E", options=list(LED_LEVELS))
    default_minutes = NumericProperty(10)
    default_intensity = NumericProperty(5)
    auto_connect = BooleanProperty(True)
    presets = ListProperty([])

    FIELDS = (
        "stim_side",
        "led_intensity",
        "default_minutes",
        "default_intensity",
        "auto_connect",
        "presets",
    )

    def __init__(self, path, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.presets = [dict(p) for p in DEFAULT_PRESETS]
        self._load()
        self.bind(**{field: self._save for field in self.FIELDS})

    def _load(self):
        data = _read_json(self.path)
        if not isinstance(data, dict):
            return
        for field in self.FIELDS:
            if field not in data:
                continue
            value = data[field]
            if field == "presets":
                if isinstance(value, list):
                    self.presets = [p for p in map(_clean_preset, value) if p]
                continue
            try:
                if field == "default_minutes":
                    value = max(MIN_MINUTES, min(MAX_MINUTES, int(value)))
                elif field == "default_intensity":
                    value = max(MIN_LEVEL, min(MAX_LEVEL, int(value)))
                elif field == "auto_connect":
                    value = bool(value)
                setattr(self, field, value)
            except (ValueError, TypeError):
                print(f"Ignoring invalid setting {field}={value!r}")

    def _save(self, *args):
        _write_json(self.path, {f: getattr(self, f) for f in self.FIELDS})

    def add_preset(self, name, minutes, intensity):
        preset = _clean_preset(
            {"name": name, "minutes": minutes, "intensity": intensity}
        )
        if not preset:
            return False
        # Replace a preset with the same name instead of duplicating it
        others = [p for p in self.presets if p["name"].lower() != preset["name"].lower()]
        self.presets = others + [preset]
        return True

    def remove_preset(self, name):
        self.presets = [p for p in self.presets if p["name"] != name]


class History(EventDispatcher):
    """Completed or stopped sessions, newest first."""

    MAX_ENTRIES = 1000

    entries = ListProperty([])

    def __init__(self, path, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        data = _read_json(path)
        if isinstance(data, list):
            self.entries = [e for e in data if isinstance(e, dict)]

    def add(self, record):
        self.entries = ([record] + list(self.entries))[: self.MAX_ENTRIES]
        _write_json(self.path, list(self.entries))

    def clear(self):
        self.entries = []
        _write_json(self.path, [])

    def stats(self):
        total = sum(int(e.get("actual_s", 0)) for e in self.entries)
        week_ago = datetime.now() - timedelta(days=7)
        week = []
        for e in self.entries:
            try:
                if datetime.fromisoformat(e["started_at"]) >= week_ago:
                    week.append(e)
            except (KeyError, TypeError, ValueError):
                pass
        return {
            "count": len(self.entries),
            "total_s": total,
            "week_count": len(week),
            "week_s": sum(int(e.get("actual_s", 0)) for e in week),
        }
