from datetime import datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, DictProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from ..device import ConnectionState
from ..storage import MAX_MINUTES, MIN_MINUTES
from ..widgets import HoverBehavior, prompt_text

KV = r"""
#:import C pulselibre.theme.C
#:import fmt_clock pulselibre.theme.fmt_clock
#:import STIM_SIDES pulselibre.device.STIM_SIDES
#:import LED_LEVELS pulselibre.device.LED_LEVELS

<PresetChip>:
    size_hint: None, None
    height: dp(34)
    width: self.texture_size[0] + dp(28)
    font_size: "13sp"
    markup: True
    color: C("text") if (self.active or self.hovered) and not self.disabled else C("text_2")
    canvas.before:
        Color:
            rgba: C("accent", .18) if self.active else (C("surface_3") if self.hovered and not self.disabled else C("surface_2"))
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.height / 2]
        Color:
            rgba: C("accent", .8) if self.active else (0, 0, 0, 0)
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, self.height / 2)
            width: 1

<SessionScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20), dp(16), dp(20), dp(16)
        spacing: dp(16)

        Banner:
            kind: "warning"
            shown: app.stop_pending
            text: "Stop not confirmed: the device may still be stimulating. It will be told to stop as soon as it reconnects. If in doubt, switch it off."

        BoxLayout:
            spacing: dp(16)

            # ---- Timer ------------------------------------------------
            Card:
                size_hint_x: .46
                SectionLabel:
                    text: "Session"
                RelativeLayout:
                    ProgressRing:
                        progress: app.session.progress
                        color: C("success") if app.session.running else C("accent")
                    BoxLayout:
                        orientation: "vertical"
                        size_hint: None, None
                        size: dp(220), dp(96)
                        pos_hint: {"center_x": .5, "center_y": .5}
                        Label:
                            text: fmt_clock(app.session.remaining)
                            font_size: "52sp"
                            bold: True
                            color: C("text")
                        Label:
                            text: root.status_text
                            font_size: "13sp"
                            color: C("text_2")
                            size_hint_y: None
                            height: dp(22)
                Stepper:
                    value: app.session.minutes
                    min: root.min_minutes
                    max: root.max_minutes
                    suffix: " min"
                    disabled: app.session.running
                    on_value: app.session.set_minutes(self.value)

            BoxLayout:
                orientation: "vertical"
                spacing: dp(16)

                # ---- Intensity ----------------------------------------
                Card:
                    size_hint_y: None
                    height: dp(196)
                    BoxLayout:
                        size_hint_y: None
                        height: dp(48)
                        BoxLayout:
                            orientation: "vertical"
                            SectionLabel:
                                text: "Intensity"
                            MutedLabel:
                                text: "Changes ramp one level at a time" if app.session.running else "Set before or during a session"
                        Label:
                            text: "[b]%d[/b][color=6B7280][size=16sp] / 9[/size][/color]" % app.session.intensity
                            markup: True
                            font_size: "40sp"
                            color: C("text")
                            size_hint_x: None
                            width: self.texture_size[0]
                    BoxLayout:
                        spacing: dp(14)
                        RoundButton:
                            text: "−"
                            pos_hint: {"center_y": .5}
                            disabled: app.session.intensity <= 1
                            on_release: app.session.set_intensity(app.session.intensity - 1)
                        IntensityMeter:
                            value: app.session.intensity
                            live: app.session.running
                            active_color: C("success") if app.session.running else C("accent")
                            on_value: app.session.set_intensity(self.value)
                        RoundButton:
                            text: "+"
                            pos_hint: {"center_y": .5}
                            disabled: app.session.intensity >= 9
                            on_release: app.session.set_intensity(app.session.intensity + 1)

                # ---- Presets ------------------------------------------
                Card:
                    BoxLayout:
                        size_hint_y: None
                        height: dp(30)
                        SectionLabel:
                            text: "Presets"
                            pos_hint: {"center_y": .5}
                        PillButton:
                            text: "Save current"
                            variant: "ghost"
                            font_size: "12sp"
                            size_hint: None, None
                            size: self.texture_size[0] + dp(24), dp(30)
                            disabled: app.session.running
                            on_release: root.save_preset()
                    ScrollView:
                        do_scroll_x: False
                        bar_width: dp(4)
                        StackLayout:
                            id: chips
                            size_hint_y: None
                            height: self.minimum_height
                            spacing: dp(8)
                    MutedLabel:
                        text: "%s side%s · LED %s · change in Settings" % (STIM_SIDES[app.settings.stim_side], "s" if app.settings.stim_side == "D" else "", LED_LEVELS[app.settings.led_intensity].lower())
                        color: C("text_3")
                        font_size: "12sp"

        PillButton:
            size_hint_y: None
            height: dp(60)
            font_size: "18sp"
            text: root.action_text
            variant: root.action_variant
            disabled: root.action_disabled
            on_release: app.primary_action()

        Label:
            size_hint_y: None
            height: dp(14)
            font_size: "12sp"
            color: C("text_3")
            text: "Space  start / stop      Up / Down  intensity      Left / Right  duration      Esc  stop"
"""


class PresetChip(HoverBehavior, ButtonBehavior, Label):
    active = BooleanProperty(False)
    preset = DictProperty({})


class SessionScreen(Screen):
    status_text = StringProperty("")
    action_text = StringProperty("Connect")
    action_variant = StringProperty("primary")
    action_disabled = BooleanProperty(False)
    min_minutes = MIN_MINUTES
    max_minutes = MAX_MINUTES

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._wire)

    def _wire(self, *args):
        app = App.get_running_app()
        app.bind(conn_state=self._refresh)
        app.session.bind(running=self._refresh, minutes=self._refresh)
        app.session.bind(
            running=self._refresh_chips,
            minutes=self._refresh_chips,
            intensity=self._refresh_chips,
        )
        app.settings.bind(presets=self._build_chips)
        self._build_chips()
        self._refresh()

    # -- state -------------------------------------------------------------

    def _refresh(self, *args):
        app = App.get_running_app()
        session = app.session
        state = app.conn_state

        if session.running:
            ends = datetime.now() + timedelta(seconds=session.remaining)
            self.status_text = f"Running · ends {ends.strftime('%H:%M')}"
            self.action_text = "Stop session"
            self.action_variant = "danger"
            self.action_disabled = False
        elif state == ConnectionState.CONNECTED:
            self.status_text = f"Ready · {int(session.minutes)} min"
            self.action_text = "Start session"
            self.action_variant = "success"
            self.action_disabled = False
        else:
            busy = {
                ConnectionState.SCANNING: "Searching for device…",
                ConnectionState.CONNECTING: "Connecting…",
                ConnectionState.RECONNECTING: "Reconnecting…",
            }
            self.status_text = "Connect a device to start"
            self.action_text = busy.get(state, "Connect to device")
            self.action_variant = "primary"
            self.action_disabled = state in busy

    # -- presets -----------------------------------------------------------

    def _build_chips(self, *args):
        app = App.get_running_app()
        box = self.ids.chips
        box.clear_widgets()
        for preset in app.settings.presets:
            chip = PresetChip(
                text=(
                    f"{preset['name']}  [color=6B7280]{preset['minutes']} min"
                    f" · {preset['intensity']}[/color]"
                ),
                preset=preset,
            )
            chip.bind(on_release=lambda c: app.session.apply_preset(c.preset))
            box.add_widget(chip)
        self._refresh_chips()

    def _refresh_chips(self, *args):
        session = App.get_running_app().session
        for chip in self.ids.chips.children:
            p = chip.preset
            chip.disabled = session.running
            chip.active = (
                p.get("minutes") == session.minutes
                and p.get("intensity") == session.intensity
            )

    def save_preset(self):
        app = App.get_running_app()
        minutes, intensity = int(app.session.minutes), int(app.session.intensity)

        def submit(name):
            if app.settings.add_preset(name, minutes, intensity):
                app.toast(f"Saved preset “{name}”", "success")

        prompt_text(
            "Save preset",
            f"{minutes} min at intensity {intensity}. "
            "A preset with the same name is replaced.",
            "Save",
            submit,
            hint="Preset name",
        )


Builder.load_string(KV)
