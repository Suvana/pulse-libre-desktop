"""Reusable themed widgets. Screens compose these; none of them know about
the device or the session."""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget

from .theme import C, lighten

TOAST_TOP_OFFSET = 76  # dp from the top of the window (header is 64dp)

KV = r"""
#:import C pulselibre.theme.C

<Screen>:
    canvas.before:
        Color:
            rgba: C("bg")
        Rectangle:
            pos: self.pos
            size: self.size

<Card>:
    orientation: "vertical"
    padding: dp(20)
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: C("surface")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
        Color:
            rgba: C("border")
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
            width: 1

<BodyLabel@Label>:
    color: C("text")
    font_size: "14sp"
    halign: "left"
    valign: "middle"
    text_size: self.width, None
    size_hint_y: None
    height: self.texture_size[1]

<MutedLabel@BodyLabel>:
    color: C("text_2")
    font_size: "13sp"

<SectionLabel>:
    color: C("text_2")
    font_size: "12sp"
    bold: True
    halign: "left"
    valign: "middle"
    text_size: self.size
    size_hint_y: None
    height: dp(18)

<PillButton>:
    color: self.fg_rgba
    font_size: "15sp"
    bold: True
    halign: "center"
    valign: "middle"
    canvas.before:
        Color:
            rgba: self.bg_rgba
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.radius if self.radius >= 0 else self.height / 2]
        Color:
            rgba: self.border_rgba
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, self.radius if self.radius >= 0 else self.height / 2)
            width: 1

<RoundButton>:
    size_hint: None, None
    size: dp(40), dp(40)
    font_size: "20sp"
    variant: "secondary"

<ProgressRing>:
    canvas:
        Color:
            rgba: self.track_color
        Line:
            circle: self.center_x, self.center_y, self.ring_radius
            width: self.thickness
        Color:
            rgba: self.color if self.progress > 0 else (0, 0, 0, 0)
        Line:
            circle: self.center_x, self.center_y, self.ring_radius, 0, max(0.5, 360 * min(1, self.progress))
            width: self.thickness
            cap: "round"

<Stepper>:
    size_hint_y: None
    height: dp(40)
    spacing: dp(12)
    RoundButton:
        text: "−"
        disabled: root.disabled or root.value <= root.min
        on_release: root.value = max(root.min, root.value - root.step)
    Label:
        text: root.display
        color: C("text") if not root.disabled else C("text_3")
        font_size: "16sp"
        bold: True
    RoundButton:
        text: "+"
        disabled: root.disabled or root.value >= root.max
        on_release: root.value = min(root.max, root.value + root.step)

<SettingRow>:
    size_hint_y: None
    height: max(dp(48), self.minimum_height)
    spacing: dp(16)
    BoxLayout:
        orientation: "vertical"
        size_hint_y: None
        height: self.minimum_height
        pos_hint: {"center_y": .5}
        BodyLabel:
            text: root.title
            bold: True
        MutedLabel:
            text: root.hint
            opacity: 1 if root.hint else 0
            height: self.texture_size[1] if root.hint else 0

<SegmentedControl>:
    size_hint: None, None
    height: dp(36)
    width: self.minimum_width
    padding: dp(3)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: C("surface_2")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

<SegmentButton>:
    size_hint_x: None
    width: max(dp(72), self.texture_size[0] + dp(24))
    font_size: "13sp"
    bold: self.active
    color: C("text") if self.active else (C("text") if self.hovered else C("text_2"))
    canvas.before:
        Color:
            rgba: C("accent") if self.active else (C("surface_3") if self.hovered else (0, 0, 0, 0))
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]

<ToggleSwitch>:
    size_hint: None, None
    size: dp(44), dp(24)
    canvas:
        Color:
            rgba: C("accent") if self.active else C("surface_3")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.height / 2]
        Color:
            rgba: C("text")
        Ellipse:
            pos: self.x + dp(3) + self._t * (self.width - self.height), self.y + dp(3)
            size: self.height - dp(6), self.height - dp(6)

<TabButton>:
    size_hint_x: None
    width: self.texture_size[0] + dp(28)
    font_size: "14sp"
    bold: self.active
    color: C("text") if self.active or self.hovered else C("text_2")
    canvas.before:
        Color:
            rgba: C("surface_2") if self.active else (C("surface_2", .5) if self.hovered else (0, 0, 0, 0))
        RoundedRectangle:
            pos: self.x, self.center_y - dp(18)
            size: self.width, dp(36)
            radius: [dp(10)]
        Color:
            rgba: C("success") if self.badge else (0, 0, 0, 0)
        Ellipse:
            pos: self.right - dp(11), self.center_y + dp(7)
            size: dp(6), dp(6)

<BatteryIcon>:
    size_hint: None, None
    size: dp(24), dp(12)
    canvas:
        Color:
            rgba: C("text_2")
        Line:
            rounded_rectangle: (self.x, self.y, self.width - dp(3), self.height, dp(2.5))
            width: 1.1
        RoundedRectangle:
            pos: self.right - dp(2), self.center_y - dp(2.5)
            size: dp(2), dp(5)
            radius: [dp(1)]
        Color:
            rgba: self.fill_color
        RoundedRectangle:
            pos: self.x + dp(2), self.y + dp(2)
            size: max(0, (self.width - dp(7)) * max(0, self.level) / 100.0), self.height - dp(4)
            radius: [dp(1.5)]

<Banner>:
    size_hint_y: None
    height: (self.texture_size[1] + dp(24)) if self.shown else 0
    opacity: 1 if self.shown else 0
    padding: dp(16), dp(12)
    color: C("text")
    font_size: "13sp"
    text_size: self.width, None
    halign: "left"
    valign: "middle"
    canvas.before:
        Color:
            rgba: C(self.kind, .16)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
        Color:
            rgba: C(self.kind, .6)
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(12))
            width: 1

<Toast>:
    size_hint: None, None
    size: min(self.texture_size[0], dp(520)) + dp(36), self.texture_size[1] + dp(22)
    text_size: (dp(520), None) if self._wide else (None, None)
    padding: dp(18), dp(11)
    font_size: "14sp"
    color: C("text")
    halign: "center"
    canvas.before:
        Color:
            rgba: C("surface_3")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
        Color:
            rgba: C(self.kind)
        RoundedRectangle:
            pos: self.x, self.y + dp(8)
            size: dp(4), self.height - dp(16)
            radius: [dp(2)]

<Dialog>:
    size_hint: None, None
    width: dp(420)
    background_color: 0, 0, 0, 0
    overlay_color: 0, 0, 0, .6
    auto_dismiss: True
    BoxLayout:
        id: box
        orientation: "vertical"
        on_minimum_height: root.height = self.minimum_height
        padding: dp(24)
        spacing: dp(16)
        canvas.before:
            Color:
                rgba: C("surface")
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(16)]
            Color:
                rgba: C("border")
            Line:
                rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
                width: 1
        BodyLabel:
            text: root.title
            font_size: "18sp"
            bold: True
        MutedLabel:
            text: root.message
            font_size: "14sp"
        BoxLayout:
            id: extra
            size_hint_y: None
            height: self.minimum_height
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(12)
            Widget
            PillButton:
                text: root.cancel_text
                variant: "ghost"
                size_hint_x: None
                width: dp(110)
                on_release: root.dismiss()
            PillButton:
                text: root.confirm_text
                variant: root.confirm_variant
                size_hint_x: None
                width: max(dp(110), self.texture_size[0] + dp(32))
                disabled: not root.can_confirm
                on_release: root._confirm()

<ThemedInput@TextInput>:
    size_hint_y: None
    height: dp(44)
    multiline: False
    write_tab: False
    padding: dp(14), (self.height - self.line_height) / 2
    font_size: "15sp"
    background_normal: ""
    background_active: ""
    background_color: C("surface_2")
    foreground_color: C("text")
    hint_text_color: C("text_3")
    cursor_color: C("accent")
    selection_color: C("accent", .35)
"""


class HoverBehavior:
    """Adds a `hovered` property that tracks the mouse pointer (desktop)."""

    hovered = BooleanProperty(False)

    def on_parent(self, widget, parent):
        if parent is not None:
            Window.bind(mouse_pos=self._on_mouse_pos)
        else:
            Window.unbind(mouse_pos=self._on_mouse_pos)
            self.hovered = False

    def _on_mouse_pos(self, window, pos):
        if self.disabled or not self.get_root_window():
            inside = False
        else:
            inside = self.collide_point(*self.to_widget(*pos))
        if inside != self.hovered:
            self.hovered = inside


class Card(BoxLayout):
    pass


class SectionLabel(Label):
    """Small caption above a group of controls."""


class PillButton(HoverBehavior, ButtonBehavior, Label):
    """Rounded button. variant: primary, success, danger, warning, secondary, ghost."""

    variant = StringProperty("primary")
    radius = NumericProperty(-1)  # -1 = fully rounded
    bg_rgba = ListProperty([0, 0, 0, 0])
    fg_rgba = ListProperty([1, 1, 1, 1])
    border_rgba = ListProperty([0, 0, 0, 0])

    FILLED = {"primary": "accent", "success": "success", "danger": "danger", "warning": "warning"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            variant=self._refresh,
            hovered=self._refresh,
            state=self._refresh,
            disabled=self._refresh,
        )
        self._refresh()

    def _refresh(self, *args):
        pressed = self.state == "down"
        if self.variant in self.FILLED:
            bg = C(self.FILLED[self.variant])
            fg = C("text")
            border = [0, 0, 0, 0]
        elif self.variant == "secondary":
            bg = C("surface_3")
            fg = C("text")
            border = [0, 0, 0, 0]
        else:  # ghost
            bg = C("surface_2") if (self.hovered or pressed) else [0, 0, 0, 0]
            fg = C("text") if self.hovered else C("text_2")
            border = C("border")
        if self.disabled:
            bg = C("surface_2") if bg[3] else bg
            fg = C("text_3")
        elif pressed:
            bg = [c * 0.85 for c in bg[:3]] + [bg[3]]
        elif self.hovered and bg[3]:
            bg = lighten(bg, 0.1)
        self.bg_rgba, self.fg_rgba, self.border_rgba = bg, fg, border


class RoundButton(PillButton):
    pass


class ProgressRing(Widget):
    progress = NumericProperty(0)  # 0..1
    thickness = NumericProperty(dp(7))
    color = ListProperty(C("accent"))
    track_color = ListProperty(C("surface_3"))
    ring_radius = NumericProperty(0)

    def on_size(self, *args):
        self.ring_radius = max(0, min(self.width, self.height) / 2 - self.thickness - dp(2))


class IntensityMeter(Widget):
    """Nine bars of rising height. Click or drag to choose a level."""

    value = NumericProperty(5)
    min = NumericProperty(1)
    max = NumericProperty(9)
    active_color = ListProperty(C("accent"))
    live = BooleanProperty(False)  # brighter colour while stimulating

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            value=self._redraw,
            disabled=self._redraw,
            live=self._redraw,
            active_color=self._redraw,
        )

    def _redraw(self, *args):
        self.canvas.clear()
        count = int(self.max - self.min + 1)
        gap = dp(6)
        bar_w = (self.width - gap * (count - 1)) / count
        if bar_w <= 0:
            return
        on = self.active_color if not self.disabled else C("text_3")
        if self.live and not self.disabled:
            on = lighten(on, 0.12)
        off = C("surface_3")
        with self.canvas:
            for i in range(count):
                level = self.min + i
                h = self.height * (0.3 + 0.7 * i / max(1, count - 1))
                Color(rgba=on if level <= self.value else off)
                RoundedRectangle(
                    pos=(self.x + i * (bar_w + gap), self.y),
                    size=(bar_w, h),
                    radius=[dp(4)],
                )

    def _level_at(self, x):
        count = int(self.max - self.min + 1)
        rel = (x - self.x) / max(1, self.width)
        return int(max(self.min, min(self.max, self.min + int(rel * count))))

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        self.value = self._level_at(touch.x)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.value = self._level_at(touch.x)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)


class Stepper(BoxLayout):
    value = NumericProperty(0)
    min = NumericProperty(0)
    max = NumericProperty(100)
    step = NumericProperty(1)
    suffix = StringProperty("")
    display = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(value=self._update, suffix=self._update)
        self._update()

    def _update(self, *args):
        self.display = f"{int(self.value)}{self.suffix}"


class SettingRow(BoxLayout):
    """A title + hint on the left; add the control as a child on the right."""

    title = StringProperty("")
    hint = StringProperty("")


class SegmentButton(HoverBehavior, ButtonBehavior, Label):
    active = BooleanProperty(False)
    option = ObjectProperty(None)


class SegmentedControl(BoxLayout):
    """options: list of (value, label). `selected` holds the chosen value."""

    options = ListProperty([])
    selected = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(options=self._build, selected=self._sync)
        Clock.schedule_once(self._build)

    def _build(self, *args):
        self.clear_widgets()
        for value, label in self.options:
            btn = SegmentButton(text=label, option=value)
            btn.bind(on_release=lambda b: setattr(self, "selected", b.option))
            self.add_widget(btn)
        self._sync()

    def _sync(self, *args):
        for btn in self.children:
            btn.active = btn.option == self.selected


class ToggleSwitch(ButtonBehavior, Widget):
    active = BooleanProperty(False)
    _t = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._t = 1 if self.active else 0

    def on_release(self):
        self.active = not self.active

    def on_active(self, instance, value):
        Animation.cancel_all(self, "_t")
        Animation(_t=1 if value else 0, d=0.15, t="out_quad").start(self)


class TabButton(HoverBehavior, ButtonBehavior, Label):
    tab = StringProperty("")
    active = BooleanProperty(False)
    badge = BooleanProperty(False)


class BatteryIcon(Widget):
    level = NumericProperty(-1)  # -1 = unknown
    charging = BooleanProperty(False)
    fill_color = ListProperty(C("text_3"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(level=self._recolor, charging=self._recolor)
        self._recolor()

    def _recolor(self, *args):
        if self.level < 0:
            self.fill_color = C("text_3")
        elif self.charging or self.level > 40:
            self.fill_color = C("success")
        elif self.level > 15:
            self.fill_color = C("warning")
        else:
            self.fill_color = C("danger")


class Banner(Label):
    """Inline coloured notice. kind: warning, danger, accent, success."""

    kind = StringProperty("warning")
    shown = BooleanProperty(True)


class Toast(Label):
    kind = StringProperty("accent")
    _wide = BooleanProperty(False)

    def on_texture_size(self, *args):
        if not self._wide and self.texture_size[0] > dp(520):
            self._wide = True


class ToastLayer(FloatLayout):
    """Transient messages along the bottom edge. Ignores touches."""

    KIND_COLORS = {
        "info": "accent",
        "success": "success",
        "warning": "warning",
        "error": "danger",
    }

    def show(self, text, kind="info", duration=3.5):
        for old in list(self.children):
            self._remove(old)
        toast = Toast(text=text, kind=self.KIND_COLORS.get(kind, "accent"), opacity=0)
        toast.pos_hint = {"center_x": 0.5}
        self.add_widget(toast)

        def place(*args):  # just below the header, clear of the main button
            toast.top = self.top - dp(TOAST_TOP_OFFSET)

        toast.bind(height=place)
        self.bind(top=place)
        place()
        Animation(opacity=1, d=0.18).start(toast)
        Clock.schedule_once(lambda dt: self._remove(toast), duration)

    def _remove(self, toast):
        if toast.parent is not self or getattr(toast, "_leaving", False):
            return
        toast._leaving = True
        anim = Animation(opacity=0, d=0.25)
        anim.bind(on_complete=lambda *a: self.remove_widget(toast))
        anim.start(toast)

    def on_touch_down(self, touch):
        return False

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        return False


class Dialog(ModalView):
    """Confirmation dialog. Put extra widgets (e.g. a text input) in ids.extra."""

    title = StringProperty("")
    message = StringProperty("")
    confirm_text = StringProperty("OK")
    cancel_text = StringProperty("Cancel")
    confirm_variant = StringProperty("primary")
    can_confirm = BooleanProperty(True)
    on_confirm = ObjectProperty(None, allownone=True)

    def _confirm(self):
        if not self.can_confirm:
            return
        self.dismiss()
        if self.on_confirm:
            self.on_confirm()


def confirm(title, message, confirm_text, on_confirm, variant="primary"):
    Dialog(
        title=title,
        message=message,
        confirm_text=confirm_text,
        confirm_variant=variant,
        on_confirm=on_confirm,
    ).open()


def prompt_text(title, message, confirm_text, on_submit, initial="", hint=""):
    """Ask for a line of text; on_submit(text) is called with the stripped value."""
    dialog = Dialog(title=title, message=message, confirm_text=confirm_text)
    field = Factory.ThemedInput(text=initial, hint_text=hint)
    dialog.ids.extra.add_widget(field)
    dialog.can_confirm = bool(initial.strip())
    field.bind(text=lambda inst, val: setattr(dialog, "can_confirm", bool(val.strip())))
    field.bind(on_text_validate=lambda inst: dialog._confirm())
    dialog.on_confirm = lambda: on_submit(field.text.strip())
    dialog.bind(on_open=lambda *a: setattr(field, "focus", True))
    dialog.open()


Factory.register("HoverBehavior", cls=HoverBehavior)
Builder.load_string(KV)
