"""BLE controller for Pulsetto devices.

This module has no Kivy dependency. All BLE work runs on a private asyncio
loop thread; the public methods are safe to call from any thread and return
immediately. State changes are reported through two callbacks, which are
invoked on the BLE thread, so a UI must marshal them onto its own thread:

    on_change()            -- some attribute below changed; re-read them
    on_event(kind, text)   -- something worth telling the user about
                              (kind: "info", "success", "warning", "error")

Readable state: state, connected, name, address, battery_percent,
battery_voltage, charging, firmware, identity, stop_pending, stimulating.
"""

import asyncio
import logging
import threading
import time
import traceback
from concurrent.futures import CancelledError

from bleak import BleakClient, BleakScanner

logging.getLogger("bleak").setLevel(logging.WARNING)

DEVICE_NAME_PREFIX = "Pulsetto"
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify

SCAN_TIMEOUT = 10.0

# Delay between single-level intensity steps sent to the device
RAMP_STEP_DELAY = 0.4

# Minimum spacing between any two writes. Measured on a Pulsetto (fw 1.1.22,
# Windows): commands sent with no gap are dropped; 50 ms was already enough.
MIN_WRITE_GAP = 0.15

# Battery voltage constants (from official APK: 3.5V=0%, 3.9V=100%)
BATTERY_FULL_VOLTAGE = 3.9
BATTERY_EMPTY_VOLTAGE = 3.5

MIN_LEVEL = 1
MAX_LEVEL = 9

# Protocol command -> label, in display order
STIM_SIDES = {"A": "Left", "D": "Both", "C": "Right"}
LED_LEVELS = {"E": "Low", "F": "Medium", "G": "High"}


class ConnectionState:
    DISCONNECTED = "disconnected"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


def battery_percentage(voltage):
    if voltage >= BATTERY_FULL_VOLTAGE:
        return 100
    if voltage <= BATTERY_EMPTY_VOLTAGE:
        return 0
    span = BATTERY_FULL_VOLTAGE - BATTERY_EMPTY_VOLTAGE
    return int(round((voltage - BATTERY_EMPTY_VOLTAGE) / span * 100))


class AsyncioLoopThread:
    """Manages a persistent asyncio event loop in a separate thread."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        """Cancel and drain pending tasks, then stop the loop and join."""

        async def drain():
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            asyncio.run_coroutine_threadsafe(drain(), self.loop).result(timeout=2)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

    def run_coroutine(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        future.add_done_callback(self._report_exception)
        return future

    @staticmethod
    def _report_exception(future):
        """Log errors from BLE tasks. Every caller fires and forgets, so without
        this an exception is stored on the Future and never seen."""
        try:
            future.result()
        except CancelledError:
            pass  # Expected when the loop is stopped on app shutdown.
        except Exception:
            print("Unhandled error in BLE task:")
            traceback.print_exc()


class PulsettoDevice:
    def __init__(self, on_change=None, on_event=None):
        self.on_change = on_change or (lambda: None)
        self.on_event = on_event or (lambda kind, text: None)

        self.state = ConnectionState.DISCONNECTED
        self.client = None
        self.name = None
        self.address = None
        self.battery_percent = None
        self.battery_voltage = None
        self.charging = None  # None = unknown
        self.firmware = None
        self.identity = None

        self.stimulating = False  # a session is (or should be) running on the device
        self.stop_pending = False  # True when a stop was not confirmed by the device
        self.target_level = 0  # intensity the user asked for
        self.device_level = 0  # last intensity actually sent to the device
        self.ramp_active = False
        self._ramping = False

        self.poll_interval = 30
        self.closing = False
        self._reconnecting = False
        self._user_disconnected = False
        self._connect_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._last_write = 0.0

        self.loop_thread = AsyncioLoopThread()
        self._submit(self._poll_loop())

    # ------------------------------------------------------------------
    # Public API (thread-safe, non-blocking)
    # ------------------------------------------------------------------

    @property
    def connected(self):
        client = self.client
        return (
            self.state == ConnectionState.CONNECTED
            and client is not None
            and client.is_connected
        )

    @property
    def busy(self):
        """True while scanning or connecting (the user should just wait)."""
        return self.state in (
            ConnectionState.SCANNING,
            ConnectionState.CONNECTING,
            ConnectionState.RECONNECTING,
        )

    def scan_and_connect(self):
        if self.connected or self.state in (
            ConnectionState.SCANNING,
            ConnectionState.CONNECTING,
        ):
            return
        self._user_disconnected = False
        self._submit(self._scan_and_connect())

    def disconnect(self):
        self._user_disconnected = True
        self._submit(self._disconnect())

    def start(self, level, side="D", led="E"):
        """Begin stimulation, ramping up to `level` one step at a time."""
        self.stimulating = True
        self.target_level = self._clamp(level)
        self._submit(self._start_device(side, led))

    def stop(self):
        self.stimulating = False
        self._submit(self._stop_device())

    def set_level(self, level):
        self.target_level = self._clamp(level)
        self._submit(self._ramp_to_target())

    def keepalive(self):
        self._submit(self._keepalive())

    def refresh(self):
        self._submit(self._query_status())

    def set_poll_interval(self, seconds):
        self.poll_interval = max(1, int(seconds))

    def enter_dfu_mode(self):
        """Reboot the device into its firmware-update bootloader. It then
        advertises as 'PulsUp', so automatic reconnect is suppressed."""
        if self.stimulating:
            return
        self._user_disconnected = True
        self._submit(self._send("U\n"))

    def shutdown(self, timeout=10):
        """Stop stimulation if needed, disconnect, and stop the loop thread.
        Blocks for up to `timeout` seconds; call on app exit."""
        self.closing = True
        if self.client and self.client.is_connected:
            future = self._submit(self._shutdown())
            try:
                future.result(timeout=timeout)
            except Exception:
                pass  # Already reported by _report_exception or timed out.
        self.loop_thread.stop()

    # ------------------------------------------------------------------
    # Internals (run on the BLE loop thread)
    # ------------------------------------------------------------------

    def _submit(self, coro):
        return self.loop_thread.run_coroutine(coro)

    @staticmethod
    def _clamp(level):
        return max(MIN_LEVEL, min(MAX_LEVEL, int(level)))

    def _notify(self):
        try:
            self.on_change()
        except Exception:
            traceback.print_exc()

    def _event(self, kind, text):
        try:
            self.on_event(kind, text)
        except Exception:
            traceback.print_exc()

    def _set_state(self, state):
        if self.state != state:
            self.state = state
            self._notify()

    async def _scan_and_connect(self, reconnect=False):
        async with self._connect_lock:
            if self.connected:
                return True
            self._set_state(
                ConnectionState.RECONNECTING if reconnect else ConnectionState.SCANNING
            )
            device = await self._scan()
            if device is None:
                self._set_state(ConnectionState.DISCONNECTED)
                if not reconnect:
                    self._event(
                        "warning",
                        "No Pulsetto found. Check that it is switched on and nearby.",
                    )
                return False

            if not reconnect:
                self._set_state(ConnectionState.CONNECTING)
            if not await self._connect(device):
                self._set_state(ConnectionState.DISCONNECTED)
                if not reconnect:
                    self._event("error", f"Couldn't connect to {device.name}.")
                return False

            self._event("success", f"Connected to {self.name}")
            if self.stop_pending:
                await self._stop_device()
            else:
                await self._query_status()
            return True

    async def _scan(self):
        try:
            device = await BleakScanner.find_device_by_filter(
                lambda d, adv: bool(d.name) and d.name.startswith(DEVICE_NAME_PREFIX),
                timeout=SCAN_TIMEOUT,
            )
        except Exception as e:
            print(f"Error during scanning: {e}")
            return None
        if device:
            print(f"Found device: {device.name} [{device.address}]")
        else:
            print("Device not found.")
        return device

    async def _connect(self, device):
        client = BleakClient(device, disconnected_callback=self._on_disconnected)
        try:
            await client.connect()
            await client.start_notify(UART_TX_CHAR_UUID, self._on_notification)
            # Adopt the client only once it is fully usable, so a half-open
            # connection's disconnect callback is ignored as stale.
            self.client = client
            self.name = device.name
            self.address = device.address
        except Exception as e:
            print(f"Failed to connect: {e}")
            try:
                await client.disconnect()
            except Exception:
                pass
            return False

        print("Connected to device.")
        self._set_state(ConnectionState.CONNECTED)
        # Query device info (firmware + identity) once, then let responses arrive
        await self._send("v\n")
        await self._send("i\n")
        await asyncio.sleep(0.5)
        return True

    def _on_disconnected(self, client):
        if client is not self.client:
            return  # a stale client from an earlier connection
        print("Device disconnected.")
        was_stimulating = self.stimulating
        self.stimulating = False
        self.ramp_active = False
        if was_stimulating:
            # Never resume stimulation automatically: make sure the device is
            # told to stop once we are connected again.
            self.stop_pending = True
            self._event(
                "warning",
                "Connection lost during the session. The device will be told "
                "to stop as soon as it reconnects.",
            )
        self._set_state(ConnectionState.DISCONNECTED)

        if self.closing or self._user_disconnected:
            return
        # Attempt to reconnect (a single loop at a time)
        if not self._reconnecting:
            self._reconnecting = True
            self._submit(self._reconnect_loop())

    async def _reconnect_loop(self, max_attempts=10):
        """Retry with exponential backoff (2s up to 30s) until connected."""
        try:
            delay = 2
            for attempt in range(1, max_attempts + 1):
                if self.closing or self.connected or self._user_disconnected:
                    return
                self._set_state(ConnectionState.RECONNECTING)
                print(f"Reconnect attempt {attempt}/{max_attempts}...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
                if self.closing or self.connected or self._user_disconnected:
                    return
                if await self._scan_and_connect(reconnect=True):
                    return
            print("Giving up on automatic reconnect.")
            self._event("error", "Couldn't reconnect. Press Connect to try again.")
        finally:
            self._reconnecting = False
            if not self.connected and self.state == ConnectionState.RECONNECTING:
                self._set_state(ConnectionState.DISCONNECTED)
            self._notify()

    async def _disconnect(self):
        if self.stimulating or self.stop_pending:
            await self._stop_device()
        if self.client and self.client.is_connected:
            await self.client.disconnect()

    async def _shutdown(self):
        if self.stimulating or self.stop_pending:
            await self._stop_device()
        await self.client.disconnect()

    async def _poll_loop(self):
        """Poll battery/charging every `poll_interval` seconds while connected."""
        waited = 0
        while not self.closing:
            await asyncio.sleep(1)
            waited += 1
            if waited >= self.poll_interval:
                waited = 0
                if self.connected:
                    await self._query_status()

    async def _query_status(self):
        await self._send("u\n")  # Get charging status
        await self._send("Q\n")  # Get battery level

    async def _send(self, command, with_response=None):
        """Send a BLE command to the device. Returns True if it was written.

        with_response: if None, '+' and '-' use writeWithResponse,
        all others use writeWithoutResponse.
        """
        client = self.client
        if client and client.is_connected:
            try:
                if with_response is None:
                    with_response = command.strip() in ("+", "-")
                # The device silently drops commands that arrive back to back
                # (e.g. "v" then "i" with no gap: neither is answered), so
                # serialize writes and keep at least MIN_WRITE_GAP between them.
                async with self._write_lock:
                    wait = self._last_write + MIN_WRITE_GAP - time.monotonic()
                    if wait > 0:
                        await asyncio.sleep(wait)
                    try:
                        await client.write_gatt_char(
                            UART_RX_CHAR_UUID, command.encode(), response=with_response
                        )
                    finally:
                        self._last_write = time.monotonic()
                print(
                    f"Sent command: {command.strip()} "
                    f"(response={'yes' if with_response else 'no'})"
                )
                return True
            except Exception as e:
                print(f"Failed to send command {command.strip()}: {e}")
        return False

    async def _start_device(self, side, led):
        # Full startup sequence (from APK beginSession — same for all devices).
        # A stop() can arrive while we sleep; check before every write so a
        # stopped session never sends another stimulation command.
        steps = [
            ("+\n", 0),  # rampUp (writeWithResponse)
            ("-\n", 0.25),  # rampDown (writeWithResponse)
            ("0\n", 0.45),  # level 0
            ("5\n", 0.45),  # brief calibration pulse
            ("0\n", 0.45),  # back to zero
        ]
        for command, pause in steps:
            if not self.stimulating:
                return
            await self._send(command)
            if pause:
                await asyncio.sleep(pause)
        if not self.stimulating:
            return
        self.device_level = 0
        self.ramp_active = True
        await self._ramp_to_target()  # step up to the target intensity
        await asyncio.sleep(0.25)
        if not self.stimulating:
            return
        # Side selection and LED intensity
        await self._send(f"{side}\n")  # D=both, A=left, C=right
        await self._send(f"{led}\n")  # E=low, F=mid, G=high
        print("Device started.")

    async def _ramp_to_target(self):
        """Move the device level toward target_level one step at a time.

        Re-reads the target every step, so changes made mid-ramp simply retarget.
        Runs only on the BLE loop thread, so the _ramping guard needs no lock."""
        if not self.ramp_active or self._ramping:
            return
        self._ramping = True
        try:
            while self.ramp_active:
                target = self.target_level
                if self.device_level == target:
                    break
                step = 1 if target > self.device_level else -1
                level = self.device_level + step
                if not await self._send(f"{level}\n"):
                    break
                self.device_level = level
                await asyncio.sleep(RAMP_STEP_DELAY)
        finally:
            self._ramping = False

    async def _stop_device(self, attempts=3):
        """Send the stop sequence, retrying on failure. Returns True only if
        every command was written; otherwise flags stop_pending so the stop is
        retried on reconnect and the UI warns the user."""
        self.ramp_active = False  # halt any in-flight ramp before stopping
        self.device_level = 0
        for attempt in range(attempts):
            # Full stop sequence (from APK endSession — same for all devices)
            results = [
                await self._send("+\n"),  # rampUp (writeWithResponse)
                await self._send("-\n"),  # rampDown (writeWithResponse)
                await self._send("-\n"),  # endSession (writeWithResponse)
            ]
            if all(results):
                print("Device stopped.")
                was_pending = self.stop_pending
                self.stop_pending = False
                self._notify()
                if was_pending:
                    self._event("success", "Device stop confirmed.")
                await self._query_status()
                return True
            if attempt < attempts - 1:
                await asyncio.sleep(0.5)
        print("WARNING: stop command could not be confirmed.")
        self.stop_pending = True
        self._notify()
        return False

    async def _keepalive(self):
        """Re-send the level the device is actually at (never the raw target)."""
        if self.ramp_active and not self._ramping:
            await self._send(f"{self.device_level}\n")

    def _on_notification(self, sender, data):
        message = data.decode("utf-8", errors="replace").strip()
        print(f"Received: {repr(message)}")

        if "Batt:" in message:
            try:
                voltage = float(message.split("Batt:")[1])
            except (IndexError, ValueError):
                return
            self.battery_voltage = voltage
            self.battery_percent = battery_percentage(voltage)
        elif message.startswith("Charging") or message.startswith("Not Charging"):
            # Text format (some firmware versions)
            self.charging = not message.startswith("Not")
        elif "u\x01" in message or message.startswith("u"):
            # Binary charging format: u<SOH>1 = charging, u<SOH>0 = not charging
            self.charging = "1" in message
        elif message.startswith("fw:"):
            self.firmware = message[3:]
        elif message.lower().startswith("pulsetto_"):
            # Device identity response (same protocol for all models)
            self.identity = message
        else:
            return
        self._notify()
