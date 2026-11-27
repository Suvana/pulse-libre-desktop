"""App screens. Each module registers its KV rules on import.

To add a screen: create a module here with a Screen subclass, import it
below, and add a tab for it in app.py (TABS).
"""

from .session import SessionScreen
from .history import HistoryScreen
from .device_info import DeviceScreen
from .settings import SettingsScreen

__all__ = ["SessionScreen", "HistoryScreen", "DeviceScreen", "SettingsScreen"]
