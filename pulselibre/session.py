"""Session lifecycle: countdown, keep-alive, poll rate and history records.

Lives outside any screen so a session keeps running while the user browses
other tabs. Must be used from the Kivy main thread.
"""

import math
import time
from datetime import datetime

from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.properties import BooleanProperty, NumericProperty

from .device import MAX_LEVEL, MIN_LEVEL
from .storage import MAX_MINUTES, MIN_MINUTES

KEEPALIVE_INTERVAL = 10  # seconds
POLL_DURING_SESSION = 3  # seconds (like the official app)
POLL_IDLE = 30
MIN_RECORDED_SECONDS = 5  # don't log accidental start/stop taps

OUTCOME_COMPLETED = "completed"
OUTCOME_STOPPED = "stopped"
OUTCOME_INTERRUPTED = "interrupted"


class SessionController(EventDispatcher):
    running = BooleanProperty(False)
    minutes = NumericProperty(10)
    duration = NumericProperty(600)  # seconds
    remaining = NumericProperty(600)  # seconds, whole
    progress = NumericProperty(0)  # 0..1 elapsed fraction
    intensity = NumericProperty(5)

    __events__ = ("on_finished",)

    def __init__(self, device, settings, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.settings = settings
        self._started_mono = None
        self._started_at = None
        self._max_intensity = 0
        self._tick_event = None
        self._keepalive_event = None
        self.set_minutes(settings.default_minutes)
        self.set_intensity(settings.default_intensity)

    # -- configuration -------------------------------------------------

    def set_minutes(self, minutes):
        if self.running:
            return
        self.minutes = max(MIN_MINUTES, min(MAX_MINUTES, int(minutes)))
        self.duration = self.minutes * 60
        self.remaining = self.duration
        self.progress = 0

    def set_intensity(self, level):
        level = max(MIN_LEVEL, min(MAX_LEVEL, int(level)))
        if level == self.intensity:
            return
        self.intensity = level
        if self.running:
            self._max_intensity = max(self._max_intensity, level)
            self.device.set_level(level)

    def apply_preset(self, preset):
        if self.running:
            return
        self.set_minutes(preset["minutes"])
        self.set_intensity(preset["intensity"])

    # -- lifecycle ------------------------------------------------------

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.running or not self.device.connected:
            return False
        self.running = True
        self._started_mono = time.monotonic()
        self._started_at = datetime.now()
        self._max_intensity = self.intensity
        self.remaining = self.duration
        self.progress = 0
        self.device.start(
            self.intensity, self.settings.stim_side, self.settings.led_intensity
        )
        self.device.set_poll_interval(POLL_DURING_SESSION)
        self._tick_event = Clock.schedule_interval(self._tick, 0.1)
        self._keepalive_event = Clock.schedule_interval(
            lambda dt: self.device.keepalive(), KEEPALIVE_INTERVAL
        )
        return True

    def stop(self, outcome=OUTCOME_STOPPED, notify_device=True):
        """End the session. With notify_device=False the caller is responsible
        for the device (e.g. it disconnected, or shutdown() will stop it)."""
        if not self.running:
            return
        elapsed = time.monotonic() - self._started_mono
        for event in (self._tick_event, self._keepalive_event):
            if event:
                event.cancel()
        self._tick_event = self._keepalive_event = None
        self.running = False
        if notify_device:
            self.device.stop()
        self.device.set_poll_interval(POLL_IDLE)
        self.remaining = self.duration
        self.progress = 0

        actual = int(min(elapsed, self.duration))
        record = {
            "started_at": self._started_at.isoformat(timespec="seconds"),
            "planned_s": int(self.duration),
            "actual_s": actual,
            "intensity": int(self.intensity),
            "max_intensity": int(self._max_intensity),
            "outcome": outcome,
        }
        self.dispatch("on_finished", record, actual >= MIN_RECORDED_SECONDS)

    def on_finished(self, record, worth_recording):
        pass

    def _tick(self, dt):
        elapsed = time.monotonic() - self._started_mono
        if elapsed >= self.duration:
            self.remaining = 0
            self.progress = 1
            self.stop(OUTCOME_COMPLETED)
            return
        self.remaining = math.ceil(self.duration - elapsed)
        self.progress = elapsed / self.duration
