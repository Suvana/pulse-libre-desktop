"""Pulse Libre desktop entry point: `poetry run python main.py`."""

import os

os.environ.setdefault("KIVY_LOG_LEVEL", "info")

# Window/input configuration must happen before kivy.core.window is imported.
from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "900")
Config.set("graphics", "height", "680")
Config.set("graphics", "minimum_width", "760")
Config.set("graphics", "minimum_height", "600")
Config.set("input", "mouse", "mouse,multitouch_on_demand")  # no red right-click dots
Config.set("kivy", "exit_on_escape", "0")  # Esc stops a session; it never quits

from pulselibre.app import PulseLibreApp  # noqa: E402

if __name__ == "__main__":
    PulseLibreApp().run()
