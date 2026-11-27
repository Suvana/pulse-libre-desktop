from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from ..session import OUTCOME_COMPLETED, OUTCOME_INTERRUPTED
from ..theme import fmt_clock, fmt_duration, fmt_when
from ..widgets import confirm

KV = r"""
#:import C pulselibre.theme.C

<StatCard@Card>:
    title: ""
    value: ""
    detail: ""
    spacing: dp(4)
    padding: dp(18), dp(14)
    SectionLabel:
        text: root.title
    Label:
        text: root.value
        font_size: "26sp"
        bold: True
        color: C("text")
        halign: "left"
        text_size: self.size
        valign: "middle"
    MutedLabel:
        text: root.detail

<HistoryRow>:
    size_hint_y: None
    height: dp(52)
    padding: dp(14), 0
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: C("surface_2")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
    Label:
        text: root.when
        color: C("text")
        bold: True
        font_size: "14sp"
        halign: "left"
        valign: "middle"
        text_size: self.size
        size_hint_x: .4
    Label:
        text: root.detail
        color: C("text_2")
        font_size: "13sp"
        halign: "left"
        valign: "middle"
        text_size: self.size
    Label:
        text: root.outcome_text
        size_hint: None, None
        size: self.texture_size[0] + dp(20), dp(24)
        pos_hint: {"center_y": .5}
        font_size: "12sp"
        bold: True
        color: C(root.outcome_color)
        canvas.before:
            Color:
                rgba: C(root.outcome_color, .15)
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [self.height / 2]

<HistoryScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20), dp(16), dp(20), dp(20)
        spacing: dp(16)

        BoxLayout:
            size_hint_y: None
            height: dp(104)
            spacing: dp(16)
            StatCard:
                title: "Sessions"
                value: root.stat_count
                detail: "all time"
            StatCard:
                title: "Total time"
                value: root.stat_total
                detail: "stimulation"
            StatCard:
                title: "Last 7 days"
                value: root.stat_week
                detail: root.stat_week_detail

        Card:
            BoxLayout:
                size_hint_y: None
                height: dp(30)
                SectionLabel:
                    text: "Recent sessions"
                    pos_hint: {"center_y": .5}
                PillButton:
                    text: "Clear history"
                    variant: "ghost"
                    font_size: "12sp"
                    size_hint: None, None
                    size: self.texture_size[0] + dp(24), dp(30)
                    disabled: not app.history.entries
                    on_release: root.clear()
            RelativeLayout:
                RecycleView:
                    id: rv
                    viewclass: "HistoryRow"
                    bar_width: dp(4)
                    RecycleBoxLayout:
                        orientation: "vertical"
                        default_size: None, dp(52)
                        default_size_hint: 1, None
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)
                BoxLayout:
                    orientation: "vertical"
                    opacity: 0 if app.history.entries else 1
                    padding: dp(24)
                    Widget
                    Label:
                        text: "No sessions yet"
                        font_size: "16sp"
                        bold: True
                        color: C("text_2")
                        size_hint_y: None
                        height: dp(24)
                    Label:
                        text: "Completed and stopped sessions will appear here."
                        font_size: "13sp"
                        color: C("text_3")
                        size_hint_y: None
                        height: dp(22)
                    Widget
"""

OUTCOMES = {
    OUTCOME_COMPLETED: ("Completed", "success"),
    OUTCOME_INTERRUPTED: ("Interrupted", "warning"),
}


class HistoryRow(BoxLayout):
    when = StringProperty("")
    detail = StringProperty("")
    outcome_text = StringProperty("")
    outcome_color = StringProperty("text_2")


class HistoryScreen(Screen):
    stat_count = StringProperty("0")
    stat_total = StringProperty("0 min")
    stat_week = StringProperty("0")
    stat_week_detail = StringProperty("sessions")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._wire)

    def _wire(self, *args):
        history = App.get_running_app().history
        history.bind(entries=self._refresh)
        self._refresh()

    def _refresh(self, *args):
        history = App.get_running_app().history
        stats = history.stats()
        self.stat_count = str(stats["count"])
        self.stat_total = fmt_duration(stats["total_s"])
        self.stat_week = str(stats["week_count"])
        self.stat_week_detail = (
            f"sessions · {fmt_duration(stats['week_s'])}"
            if stats["week_count"]
            else "sessions"
        )

        rows = []
        for e in history.entries:
            label, color = OUTCOMES.get(e.get("outcome"), ("Stopped early", "text_2"))
            actual, planned = e.get("actual_s", 0), e.get("planned_s", 0)
            intensity, peak = e.get("intensity", "?"), e.get("max_intensity")
            level = f"intensity {intensity}"
            if peak and peak != intensity:
                level += f" (peak {peak})"
            rows.append(
                {
                    "when": fmt_when(e.get("started_at")),
                    "detail": f"{fmt_clock(actual)} of {fmt_clock(planned)} · {level}",
                    "outcome_text": label,
                    "outcome_color": color,
                }
            )
        self.ids.rv.data = rows

    def clear(self):
        history = App.get_running_app().history
        confirm(
            "Clear history?",
            f"This permanently deletes all {len(history.entries)} recorded sessions.",
            "Clear history",
            history.clear,
            variant="danger",
        )


Builder.load_string(KV)
