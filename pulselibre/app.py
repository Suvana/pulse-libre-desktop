import os

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.modalview import ModalView

from . import screens  # noqa: F401  (registers screen classes + KV)
from . import widgets  # noqa: F401  (registers widget KV)
from .device import ConnectionState, PulsettoDevice
from .session import OUTCOME_COMPLETED, OUTCOME_INTERRUPTED, SessionController
from .storage import History, Settings
from .theme import C, fmt_duration

# (screen name, tab label). Order = tab order = Ctrl+1..n
TABS = [
    ("session", "Session"),
    ("history", "History"),
    ("device", "Device"),
    ("settings", "Settings"),
]

KV = r"""
#:import C pulselibre.theme.C
#:import NoTransition kivy.uix.screenmanager.NoTransition

<StatusPill@HoverBehavior+ButtonBehavior+BoxLayout>:
    size_hint: None, None
    height: dp(36)
    width: self.minimum_width
    padding: dp(14), 0
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: C("surface_3") if self.hovered else C("surface_2")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.height / 2]
    Widget:
        size_hint_x: None
        width: dp(8)
        canvas:
            Color:
                rgba: app.status_color
            Ellipse:
                pos: self.center_x - dp(4), self.center_y - dp(4)
                size: dp(8), dp(8)
    Label:
        text: app.status_text
        font_size: "13sp"
        bold: True
        color: C("text")
        size_hint_x: None
        width: self.texture_size[0]
    Widget:
        size_hint_x: None
        width: dp(1) if app.battery >= 0 else 0
        canvas:
            Color:
                rgba: C("border") if app.battery >= 0 else (0, 0, 0, 0)
            Rectangle:
                pos: self.x, self.center_y - dp(8)
                size: dp(1), dp(16)
    BatteryIcon:
        level: app.battery
        charging: app.charging
        pos_hint: {"center_y": .5}
        opacity: 1 if app.battery >= 0 else 0
        width: dp(24) if app.battery >= 0 else 0
    Label:
        text: ("%d%%" % app.battery + (" · charging" if app.charging else "")) if app.battery >= 0 else ""
        font_size: "13sp"
        color: C("text_2")
        size_hint_x: None
        width: self.texture_size[0]

<Root@FloatLayout>:
    BoxLayout:
        orientation: "vertical"
        BoxLayout:
            id: header
            size_hint_y: None
            height: dp(64)
            padding: dp(20), 0
            spacing: dp(6)
            canvas.before:
                Color:
                    rgba: C("surface")
                Rectangle:
                    pos: self.pos
                    size: self.size
                Color:
                    rgba: C("border")
                Rectangle:
                    pos: self.x, self.y
                    size: self.width, 1
            Label:
                text: "Pulse Libre"
                font_size: "18sp"
                bold: True
                color: C("text")
                size_hint_x: None
                width: self.texture_size[0] + dp(18)
                halign: "left"
            BoxLayout:
                id: tabs
                spacing: dp(2)
                size_hint_x: None
                width: self.minimum_width
            Widget
            StatusPill:
                pos_hint: {"center_y": .5}
                on_release: app.current_tab = "device"
        ScreenManager:
            id: sm
            transition: NoTransition()
            SessionScreen:
                name: "session"
            HistoryScreen:
                name: "history"
            DeviceScreen:
                name: "device"
            SettingsScreen:
                name: "settings"
    ToastLayer:
        id: toasts
"""

STATUS = {
    ConnectionState.CONNECTED: ("Connected", "success"),
    ConnectionState.SCANNING: ("Searching…", "warning"),
    ConnectionState.CONNECTING: ("Connecting…", "warning"),
    ConnectionState.RECONNECTING: ("Reconnecting…", "warning"),
    ConnectionState.DISCONNECTED: ("Not connected", "text_3"),
}

KEY_ESC, KEY_SPACE = 27, 32
KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN = 275, 276, 273, 274


class PulseLibreApp(App):
    title = "Pulse Libre"

    device = ObjectProperty(None)
    session = ObjectProperty(None)
    settings = ObjectProperty(None)
    history = ObjectProperty(None)
    current_tab = StringProperty("session")

    # Device state mirrored onto the main thread for KV bindings
    conn_state = StringProperty(ConnectionState.DISCONNECTED)
    connected = BooleanProperty(False)
    device_busy = BooleanProperty(False)
    device_name = StringProperty("")
    device_address = StringProperty("")
    identity = StringProperty("")
    firmware = StringProperty("")
    battery = NumericProperty(-1)
    battery_voltage = NumericProperty(0)
    charging = BooleanProperty(False)
    charging_known = BooleanProperty(False)
    stop_pending = BooleanProperty(False)
    status_text = StringProperty("Not connected")
    status_color = ListProperty(C("text_3"))

    def build(self):
        Window.clearcolor = C("bg")
        Window.minimum_width, Window.minimum_height = dp(760), dp(600)

        data_dir = self.user_data_dir
        self.settings = Settings(os.path.join(data_dir, "settings.json"))
        self.history = History(os.path.join(data_dir, "history.json"))
        self._sync_scheduled = False
        self.device = PulsettoDevice(
            on_change=self._device_changed, on_event=self._device_event
        )
        self.session = SessionController(self.device, self.settings)
        self.session.bind(on_finished=self._session_finished)

        Builder.load_string(KV)
        from kivy.factory import Factory

        root = Factory.Root()
        self._build_tabs(root)
        self.bind(current_tab=lambda *a: setattr(root.ids.sm, "current", self.current_tab))
        Window.bind(on_key_down=self._on_key_down)

        if self.settings.auto_connect:
            self.device.scan_and_connect()
        return root

    def _build_tabs(self, root):
        from .widgets import TabButton

        for name, label in TABS:
            tab = TabButton(text=label, tab=name, active=name == self.current_tab)
            tab.bind(on_release=lambda t: setattr(self, "current_tab", t.tab))
            self.bind(current_tab=lambda inst, cur, t=tab: setattr(t, "active", t.tab == cur))
            if name == "session":
                self.session.bind(running=tab.setter("badge"))
            root.ids.tabs.add_widget(tab)

    # -- device -> UI (callbacks arrive on the BLE thread) -----------------

    def _device_changed(self):
        if not self._sync_scheduled:
            self._sync_scheduled = True
            Clock.schedule_once(self._sync_device)

    def _device_event(self, kind, text):
        Clock.schedule_once(lambda dt: self.toast(text, kind))

    def _sync_device(self, dt):
        self._sync_scheduled = False
        d = self.device
        self.conn_state = d.state
        self.connected = d.connected
        self.device_busy = d.busy
        self.device_name = d.name or ""
        self.device_address = d.address or ""
        self.identity = d.identity or ""
        self.firmware = d.firmware or ""
        self.battery = d.battery_percent if d.battery_percent is not None else -1
        self.battery_voltage = d.battery_voltage or 0
        self.charging_known = d.charging is not None
        self.charging = bool(d.charging)
        self.stop_pending = d.stop_pending

        if self.stop_pending:
            self.status_text, color = "Stop unconfirmed", "warning"
        else:
            self.status_text, color = STATUS.get(d.state, ("Not connected", "text_3"))
        self.status_color = C(color)

        # The device already flagged stop_pending; just end the session locally
        if self.session.running and not self.connected:
            self.session.stop(OUTCOME_INTERRUPTED, notify_device=False)

    # -- session -----------------------------------------------------------

    def primary_action(self):
        if self.session.running:
            self.session.stop()
        elif self.connected:
            self.session.start()
        elif not self.device_busy:
            self.device.scan_and_connect()

    def _session_finished(self, session, record, worth_recording):
        if worth_recording:
            self.history.add(record)
        if record["outcome"] == OUTCOME_COMPLETED:
            self.toast(f"Session complete · {fmt_duration(record['actual_s'])}", "success")

    # -- misc --------------------------------------------------------------

    def toast(self, text, kind="info"):
        if self.root:
            self.root.ids.toasts.show(text, kind)

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        if any(isinstance(w, ModalView) for w in Window.children):
            return False
        if "ctrl" in modifiers and ord("1") <= key < ord("1") + len(TABS):
            self.current_tab = TABS[key - ord("1")][0]
            return True
        if key == KEY_ESC:
            # Esc never quits the app (see main.py); it is the "stop now" key.
            if self.session.running:
                self.session.stop()
            return True
        # Text entry only happens inside dialogs, which are excluded above.
        if self.current_tab != "session":
            return False
        if key == KEY_SPACE:
            self.primary_action()
        elif key == KEY_UP:
            self.session.set_intensity(self.session.intensity + 1)
        elif key == KEY_DOWN:
            self.session.set_intensity(self.session.intensity - 1)
        elif key == KEY_RIGHT:
            self.session.set_minutes(self.session.minutes + 1)
        elif key == KEY_LEFT:
            self.session.set_minutes(self.session.minutes - 1)
        else:
            return False
        return True

    def on_stop(self):
        # Close out the session record, then let the device layer stop the
        # stimulation and disconnect before the loop thread is shut down.
        if self.session.running:
            self.session.stop(notify_device=False)
        self.device.shutdown()
