from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import DictProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from ..device import MAX_LEVEL, MIN_LEVEL
from ..storage import MAX_MINUTES, MIN_MINUTES
from ..widgets import confirm

KV = r"""
#:import C pulselibre.theme.C

<PresetRow>:
    size_hint_y: None
    height: dp(44)
    padding: dp(14), 0, dp(6), 0
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: C("surface_2")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
    Label:
        text: root.preset.get("name", "")
        bold: True
        color: C("text")
        font_size: "14sp"
        halign: "left"
        valign: "middle"
        text_size: self.size
        shorten: True
    Label:
        text: "%s min  ·  intensity %s" % (root.preset.get("minutes", "?"), root.preset.get("intensity", "?"))
        color: C("text_2")
        font_size: "13sp"
        size_hint_x: None
        width: dp(170)
        halign: "right"
        valign: "middle"
        text_size: self.size
    PillButton:
        text: "Remove"
        variant: "ghost"
        font_size: "12sp"
        size_hint: None, None
        size: dp(80), dp(30)
        pos_hint: {"center_y": .5}
        on_release: root.remove()

<SettingsScreen>:
    ScrollView:
        do_scroll_x: False
        bar_width: dp(4)
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height
            padding: dp(20), dp(16), dp(20), dp(20)
            spacing: dp(16)

            Card:
                size_hint_y: None
                height: self.minimum_height
                SectionLabel:
                    text: "Defaults"
                SettingRow:
                    title: "Session length"
                    hint: "Used when the app starts."
                    Stepper:
                        size_hint_x: None
                        width: dp(180)
                        pos_hint: {"center_y": .5}
                        min: root.min_minutes
                        max: root.max_minutes
                        suffix: " min"
                        value: app.settings.default_minutes
                        on_value: app.settings.default_minutes = int(self.value)
                SettingRow:
                    title: "Intensity"
                    hint: "Starting intensity when the app starts."
                    Stepper:
                        size_hint_x: None
                        width: dp(180)
                        pos_hint: {"center_y": .5}
                        min: root.min_level
                        max: root.max_level
                        value: app.settings.default_intensity
                        on_value: app.settings.default_intensity = int(self.value)
                SettingRow:
                    title: "Connect on launch"
                    hint: "Search for a Pulsetto automatically when the app opens."
                    ToggleSwitch:
                        pos_hint: {"center_y": .5}
                        active: app.settings.auto_connect
                        on_active: app.settings.auto_connect = self.active

            Card:
                size_hint_y: None
                height: self.minimum_height
                SectionLabel:
                    text: "Presets"
                MutedLabel:
                    text: "Save new presets from the Session tab with “Save current”."
                BoxLayout:
                    id: preset_list
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(6)
                BoxLayout:
                    size_hint_y: None
                    height: dp(36)
                    Widget
                    PillButton:
                        text: "Restore defaults"
                        variant: "ghost"
                        font_size: "12sp"
                        size_hint: None, None
                        size: self.texture_size[0] + dp(24), dp(30)
                        pos_hint: {"center_y": .5}
                        on_release: root.restore_presets()
"""


class PresetRow(BoxLayout):
    preset = DictProperty({})

    def remove(self):
        app = App.get_running_app()
        name = self.preset.get("name", "")
        confirm(
            "Remove preset?",
            f"“{name}” will be removed from your presets.",
            "Remove",
            lambda: app.settings.remove_preset(name),
            variant="danger",
        )


class SettingsScreen(Screen):
    min_minutes = MIN_MINUTES
    max_minutes = MAX_MINUTES
    min_level = MIN_LEVEL
    max_level = MAX_LEVEL

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._wire)

    def _wire(self, *args):
        App.get_running_app().settings.bind(presets=self._build_presets)
        self._build_presets()

    def _build_presets(self, *args):
        box = self.ids.preset_list
        box.clear_widgets()
        for preset in App.get_running_app().settings.presets:
            box.add_widget(PresetRow(preset=preset))

    def restore_presets(self):
        from ..storage import DEFAULT_PRESETS

        settings = App.get_running_app().settings
        confirm(
            "Restore default presets?",
            "Your current presets will be replaced by the built-in ones.",
            "Restore",
            lambda: setattr(settings, "presets", [dict(p) for p in DEFAULT_PRESETS]),
        )


Builder.load_string(KV)
