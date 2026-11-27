from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen

from ..widgets import confirm

KV = r"""
#:import C pulselibre.theme.C

<InfoRow@BoxLayout>:
    key: ""
    value: ""
    size_hint_y: None
    height: dp(34)
    Label:
        text: root.key
        color: C("text_2")
        font_size: "14sp"
        halign: "left"
        valign: "middle"
        text_size: self.size
        size_hint_x: None
        width: dp(140)
    Label:
        text: root.value or "—"
        color: C("text") if root.value else C("text_3")
        font_size: "14sp"
        halign: "left"
        valign: "middle"
        text_size: self.size
        shorten: True
        shorten_from: "right"

<DeviceScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20), dp(16), dp(20), dp(20)
        spacing: dp(16)

        Card:
            size_hint_y: None
            height: self.minimum_height
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(12)
                BoxLayout:
                    orientation: "vertical"
                    Label:
                        text: app.device_name or "No device"
                        font_size: "20sp"
                        bold: True
                        color: C("text")
                        halign: "left"
                        valign: "middle"
                        text_size: self.size
                    Label:
                        text: app.status_text
                        font_size: "13sp"
                        color: app.status_color
                        halign: "left"
                        valign: "middle"
                        text_size: self.size
                        size_hint_y: None
                        height: dp(16)
                PillButton:
                    text: "Refresh"
                    variant: "ghost"
                    size_hint: None, None
                    size: dp(100), dp(40)
                    disabled: not app.connected
                    on_release: app.device.refresh()
                PillButton:
                    text: "Disconnect" if app.connected else "Connect"
                    variant: "secondary" if app.connected else "primary"
                    size_hint: None, None
                    size: dp(120), dp(40)
                    disabled: app.device_busy or app.session.running
                    on_release: root.toggle_connection()
            Widget:
                size_hint_y: None
                height: dp(4)
            InfoRow:
                key: "Model"
                value: app.identity
            InfoRow:
                key: "Firmware"
                value: app.firmware
            InfoRow:
                key: "Address"
                value: app.device_address
            InfoRow:
                key: "Battery"
                value: ("%d%%  ·  %.2f V" % (app.battery, app.battery_voltage)) if app.battery >= 0 else ""
            InfoRow:
                key: "Charging"
                value: ("Yes" if app.charging else "No") if app.charging_known else ""

        Card:
            size_hint_y: None
            height: self.minimum_height
            SectionLabel:
                text: "Firmware update"
            MutedLabel:
                text: "DFU mode reboots the device into its bootloader so new firmware can be flashed with a Nordic DFU tool. The charger must be connected. While in DFU mode the device advertises as “PulsUp” and this app can't control it."
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                MutedLabel:
                    text: "" if not app.connected else ("Stop the session first." if app.session.running else ("Connect the charger first." if app.charging_known and not app.charging else ""))
                    color: C("warning")
                    pos_hint: {"center_y": .5}
                PillButton:
                    text: "Enter DFU mode…"
                    variant: "danger"
                    size_hint: None, None
                    size: dp(170), dp(40)
                    disabled: not app.connected or app.session.running or (app.charging_known and not app.charging)
                    on_release: root.enter_dfu()

        Widget
"""


class DeviceScreen(Screen):
    def toggle_connection(self):
        app = App.get_running_app()
        if app.connected:
            app.device.disconnect()
        else:
            app.device.scan_and_connect()

    def enter_dfu(self):
        app = App.get_running_app()

        def go():
            app.device.enter_dfu_mode()
            app.toast("DFU command sent. The device will reboot into its bootloader.", "info")

        confirm(
            "Enter DFU mode?",
            "The device will disconnect and reboot into its firmware-update "
            "bootloader. Only do this if you are about to flash firmware.",
            "Enter DFU mode",
            go,
            variant="danger",
        )


Builder.load_string(KV)
