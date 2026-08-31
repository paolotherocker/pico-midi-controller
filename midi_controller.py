"""Top-level MidiController: polls control hardware, drives the SNAP,
preset, looper, and value managers, sends the resulting MIDI messages
over USB, and refreshes the NeoPixel array and display accordingly.
"""

import time
from collections import deque
from tm1637 import TM1637
from utils.neopixelmanager import NeoPixelManager, Off
from utils.midi import Message, MidiUsb
from control_hardware import (
    Control,
    ControlButton,
    ControlEncoder,
    ControlAction,
    LEDMode,
)
from managers import (
    ConfigError,
    MidiMap,
    PatternMap,
    SnapManager,
    PresetManager,
    LooperManager,
    ValueParam,
    ValueManager,
    _PATCH_MAP,
)

MIDI_INTERVAL_MS = 8


class MidiController:
    """Generates MIDI messages from control hardware, sends them over
    USB, and refreshes the LEDs and display."""

    _MSG_QUEUE_MAXLEN = 256

    _SNAP_ACTIONS = (
        ControlAction.SNAP_1_2,
        ControlAction.SNAP_3_4,
        ControlAction.SNAP_5_6,
        ControlAction.SNAP_7_8,
    )

    _LOOPER_ACTIONS = (
        ControlAction.LOOPER_REC_OD,
        ControlAction.LOOPER_STOP_PLAY,
        ControlAction.LOOPER_UNDO,
        ControlAction.LOOPER_CLEAR,
    )

    _VALUE_ACTIONS = (
        ControlAction.VALUE_UP,
        ControlAction.VALUE_DOWN,
        ControlAction.VALUE_TOGGLE,
    )

    def __init__(
        self,
        control_buttons: list[ControlButton],
        np: NeoPixelManager,
        display: TM1637,
        midi_map: MidiMap,
        midi: MidiUsb,
        preset_num: int = 8,
        pattern_map: PatternMap = PatternMap(),
        send_mode_msg: bool = False,
        led_map: list[LEDMode] = None,
        control_encoder: ControlEncoder = None,
        value_params: list[ValueParam] = None,
        value_hang_ms: int = 1000,
    ):
        """
        Args:
            control_buttons (list[ControlButton]): Buttons to poll.
            np (NeoPixelManager): NeoPixel array manager.
            display (TM1637): Display manager.
            midi_map (MidiMap): MIDI channel and CC configuration.
            midi (MidiUsb): USB MIDI output used to send queued messages.
            preset_num (int, optional): Number of presets. Defaults to 8.
            pattern_map (PatternMap, optional): LED patterns to use.
                Defaults to all off.
            send_mode_msg (bool, optional): Send a mode message before each
                snap message. Defaults to False.
            led_map (list[LEDMode], optional): LED mode for each NeoPixel
                group, in order. Defaults to None.
            control_encoder (ControlEncoder, optional): Encoder to poll.
                Defaults to None.
            value_params (list[ValueParam], optional): Value targets.
                Defaults to None.
            value_hang_ms (int, optional): How long a value stays on the
                display after changing. Defaults to 1000.

        Raises:
            RuntimeError: If the configuration is invalid, or the message
                queue overflows during operation. All NeoPixel groups are
                turned off and the display shows "E<code>" (see
                ConfigError) before raising.
        """
        self.np = np
        self.display = display
        self.midi = midi
        self.pattern_map = pattern_map
        self.send_mode_msg = send_mode_msg
        self.led_map = led_map or []

        # Tracks the Pattern instance last applied to each NeoPixel group,
        # so set_pattern() is only called on an actual change. Calling it
        # every update() would reset each pattern's internal start time
        # and freeze animated patterns (Pulse, Flash, Wave) at t=0.
        self._led_pattern: list = [None] * len(self.led_map)

        self.value = (
            ValueManager(midi_map=midi_map, params=value_params, hang_ms=value_hang_ms)
            if value_params is not None
            else None
        )

        # Manager instances
        self.snap = SnapManager(midi_map=midi_map, pattern_map=pattern_map)
        self.preset = PresetManager(midi_map=midi_map, preset_num=preset_num)
        self.looper = LooperManager(midi_map=midi_map, pattern_map=pattern_map)

        self._hardware: list[Control] = list(control_buttons)
        if control_encoder is not None:
            self._hardware.append(control_encoder)

        self._validate_config(control_buttons, control_encoder, value_params)

        # MIDI message queue
        self.msg_queue = deque((), self._MSG_QUEUE_MAXLEN)
        self.msg_time: int = 0

        self.display.brightness(3)
        self.display.show("    ")

    def _configured_actions(
        self, control_buttons: list[ControlButton], control_encoder: ControlEncoder
    ) -> set:
        """Every ControlAction assigned to any piece of control hardware."""
        actions = set()
        for ctrl in control_buttons:
            actions.add(ctrl.action_pressed)
            actions.add(ctrl.action_short)
            actions.add(ctrl.action_long)
        if control_encoder is not None:
            actions.add(control_encoder.action_cw)
            actions.add(control_encoder.action_ccw)
        return actions

    def _fail(self, code: int):
        """Turns off all NeoPixel groups, shows an error code on the
        display, and halts."""
        self.np.clear()
        self.np.write()
        self.display.show("E{:03d}".format(code))
        raise RuntimeError("MidiController error E{:03d}".format(code))

    def _validate_config(
        self,
        control_buttons: list[ControlButton],
        control_encoder: ControlEncoder,
        value_params: list[ValueParam],
    ):
        """Checks for configuration problems serious enough to prevent
        starting, and shows an error code instead of failing later."""
        # led_map must fit within the NeoPixel array's actual groups
        try:
            for np_id in range(len(self.led_map)):
                self.np.set_pattern(pattern=Off(), id=np_id)
        except Exception:
            self._fail(ConfigError.LED_MAP_SIZE)

        configured = self._configured_actions(control_buttons, control_encoder)

        # Value actions need value_params to be set
        if configured & set(self._VALUE_ACTIONS) and self.value is None:
            self._fail(ConfigError.VALUE_UNCONFIGURED)

        # Each value target's range must make sense
        if value_params:
            for param in value_params:
                if param.min_value > param.max_value:
                    self._fail(ConfigError.VALUE_RANGE)

    def _handle_action(self, action: ControlAction):
        """Handles a single action."""
        if action == ControlAction.NONE:
            return

        if action in self._SNAP_ACTIONS:
            self.snap.exec_action(action)
            if self.send_mode_msg == True:
                self.msg_queue.append(self.snap.snap_mode_msg())
            self.msg_queue.append(self.snap.msg())

        elif action in (ControlAction.PRESET_UP, ControlAction.PRESET_DOWN):
            self.preset.exec_action(action)
            self.msg_queue.append(self.preset.msg())
            self.snap.reset()
            self.msg_queue.append(self.snap.msg())

        elif action in self._LOOPER_ACTIONS:
            self.looper.exec_action(action)
            self.msg_queue.append(self.looper.msg())

        elif action in self._VALUE_ACTIONS:
            if self.value:
                self.value.exec_action(action)
                self.msg_queue.append(self.value.msg())

        if len(self.msg_queue) >= self._MSG_QUEUE_MAXLEN:
            self._fail(ConfigError.QUEUE_OVERFLOW)

    def _refresh_leds(self):
        """Applies each NeoPixel group's current pattern, but only calls
        set_pattern() when the pattern actually changed. Re-applying an
        unchanged pattern every frame would reset its start time and
        freeze animated patterns (Pulse, Flash, Wave)."""
        for np_id, led_mode in enumerate(self.led_map):
            pattern = None
            if led_mode in SnapManager._ACTION_BY_LED_MODE:
                pattern = self.snap.pattern(led_mode)
            elif led_mode == LEDMode.LOOPER:
                pattern = self.looper.pattern()

            if pattern is not None and pattern is not self._led_pattern[np_id]:
                self.np.set_pattern(pattern=pattern, id=np_id)
                self._led_pattern[np_id] = pattern

    def update(self):
        for ctrl in self._hardware:
            self._handle_action(ctrl.update())

        self._refresh_leds()

        # Refresh Display
        if self.value and self.value.is_active():
            self.display.show(self.value.display_str())
        else:
            self.display.show(f"   {_PATCH_MAP[self.preset.value()]}")

        self.np.poll()

        now = time.ticks_ms()
        if time.ticks_diff(now, self.msg_time) > MIDI_INTERVAL_MS:
            if len(self.msg_queue) > 0:
                self.msg_time = now
                msg: Message = self.msg_queue.popleft()
                if self.midi.is_open():
                    self.midi.send_message(msg)
