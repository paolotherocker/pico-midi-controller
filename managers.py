"""State managers for the MIDI controller: SNAP groups, presets, the
looper transport, and value targets. Also holds their shared
configuration types (MidiMap, PatternMap, ValueParam) and the
ConfigError codes surfaced by MidiController.
"""

import time
from utils.neopixelmanager import Pattern, Off
from utils.midi import ControlChange
from control_hardware import ControlAction, LEDMode

_PATCH_MAP = [" "] + [chr(ord("A") + i) for i in range(26)]
MAX_PRESET_NUM = len(_PATCH_MAP) - 1


def _clamp_byte(value: int) -> int:
    """Clamp to the valid 7-bit MIDI data byte range (0-127)."""
    if value is None:
        return None
    return max(0, min(127, value))


def _clamp_channel(value: int) -> int:
    """Clamp to the valid 4-bit MIDI channel range (0-15)."""
    if value is None:
        return None
    return max(0, min(15, value))


class ConfigError:
    """Error codes shown on the display when MidiController detects a
    problem it can't safely continue from."""

    LED_MAP_SIZE = 1
    VALUE_RANGE = 2
    VALUE_UNCONFIGURED = 3
    QUEUE_OVERFLOW = 4


class MidiMap:
    CHANNEL: int
    SNAP_CC: int
    SNAP_MODE_VAL: int
    PRESET_CC: int
    PRESET_UP_VAL: int
    PRESET_DOWN_VAL: int
    LOOPER_CC: int
    LOOPER_RO_VAL: int
    LOOPER_SP_VAL: int
    LOOPER_UNDO_VAL: int
    LOOPER_CLEAR_VAL: int

    def __init__(
        self,
        channel: int,
        snap_cc: int,
        snap_mode_val: int,
        preset_cc: int,
        preset_up_val: int,
        preset_down_val: int,
        looper_cc: int,
        looper_ro_val: int,
        looper_sp_val: int,
        looper_undo_val: int,
        looper_clear_val: int,
    ):
        self.CHANNEL = _clamp_channel(channel)
        self.SNAP_CC = _clamp_byte(snap_cc)
        self.SNAP_MODE_VAL = _clamp_byte(snap_mode_val)
        self.PRESET_CC = _clamp_byte(preset_cc)
        self.PRESET_UP_VAL = _clamp_byte(preset_up_val)
        self.PRESET_DOWN_VAL = _clamp_byte(preset_down_val)
        self.LOOPER_CC = _clamp_byte(looper_cc)
        self.LOOPER_RO_VAL = _clamp_byte(looper_ro_val)
        self.LOOPER_SP_VAL = _clamp_byte(looper_sp_val)
        self.LOOPER_UNDO_VAL = _clamp_byte(looper_undo_val)
        self.LOOPER_CLEAR_VAL = _clamp_byte(looper_clear_val)


class PatternMap:
    """NeoPixel patterns for each LED state. Unset patterns stay off."""

    SNAP_ACTIVE: Pattern
    SNAP_ACTIVE_SEC: Pattern
    SNAP_PASSIVE: Pattern
    SNAP_PASSIVE_SEC: Pattern
    LOOPER_EMPTY: Pattern
    LOOPER_RECORDING: Pattern
    LOOPER_PLAYING: Pattern
    LOOPER_OVERDUBBING: Pattern
    LOOPER_STOPPED: Pattern

    def __init__(
        self,
        snap_active: Pattern = Off(),
        snap_active_sec: Pattern = Off(),
        snap_passive: Pattern = Off(),
        snap_passive_sec: Pattern = Off(),
        looper_empty: Pattern = Off(),
        looper_recording: Pattern = Off(),
        looper_playing: Pattern = Off(),
        looper_overdubbing: Pattern = Off(),
        looper_stopped: Pattern = Off(),
    ):
        self.SNAP_ACTIVE = snap_active
        self.SNAP_ACTIVE_SEC = snap_active_sec
        self.SNAP_PASSIVE = snap_passive
        self.SNAP_PASSIVE_SEC = snap_passive_sec
        self.LOOPER_EMPTY = looper_empty
        self.LOOPER_RECORDING = looper_recording
        self.LOOPER_PLAYING = looper_playing
        self.LOOPER_OVERDUBBING = looper_overdubbing
        self.LOOPER_STOPPED = looper_stopped


class SnapManager:
    """Tracks which of the four SNAP groups is active and each group's
    secondary value. Only one group is active at a time; pressing the
    active group again toggles its secondary value."""

    _BASE_VALUE = {
        ControlAction.SNAP_1_2: 1,
        ControlAction.SNAP_3_4: 3,
        ControlAction.SNAP_5_6: 5,
        ControlAction.SNAP_7_8: 7,
    }

    _ACTION_BY_LED_MODE = {
        LEDMode.SNAP_1_2: ControlAction.SNAP_1_2,
        LEDMode.SNAP_3_4: ControlAction.SNAP_3_4,
        LEDMode.SNAP_5_6: ControlAction.SNAP_5_6,
        LEDMode.SNAP_7_8: ControlAction.SNAP_7_8,
    }

    def __init__(self, midi_map: MidiMap, pattern_map: PatternMap):
        self.midi_map = midi_map
        self.pattern_map = pattern_map
        self.active_action = None
        self._secondary = {}
        self._value = 0

        self._snap_mode_msg = ControlChange(
            channel=midi_map.CHANNEL,
            controller=midi_map.SNAP_CC,
            value=midi_map.SNAP_MODE_VAL,
        )

    def exec_action(self, control_action: ControlAction):
        """Updates state for a SNAP press. Retrieve the resulting message
        via msg()."""
        secondary = self._secondary.get(control_action, False)
        if self.active_action == control_action:
            secondary = not secondary
        self.active_action = control_action
        self._secondary[control_action] = secondary

        self._value = self._BASE_VALUE[control_action] + secondary

    def snap_mode_msg(self) -> ControlChange:
        return self._snap_mode_msg

    def msg(self) -> ControlChange:
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=self.midi_map.SNAP_CC,
            value=self._value,
        )

    def value(self) -> int:
        return self._value

    def pattern(self, led_mode: LEDMode) -> Pattern:
        """LED pattern for a SNAP group."""
        control_action = self._ACTION_BY_LED_MODE[led_mode]
        secondary = self._secondary.get(control_action, False)
        if control_action == self.active_action:
            return (
                self.pattern_map.SNAP_ACTIVE_SEC
                if secondary
                else self.pattern_map.SNAP_ACTIVE
            )

        return (
            self.pattern_map.SNAP_PASSIVE_SEC
            if secondary
            else self.pattern_map.SNAP_PASSIVE
        )


class PresetManager:
    """Owns the current preset number and its wraparound logic."""

    def __init__(self, midi_map: MidiMap, preset_num: int = 8, initial: int = 1):
        self.midi_map = midi_map
        self.preset_num = max(1, min(MAX_PRESET_NUM, preset_num))
        self._value = max(1, min(self.preset_num, initial))
        self._msg_value = midi_map.PRESET_UP_VAL

    def exec_action(self, control_action: ControlAction):
        """Updates the preset number. Retrieve the resulting message via
        msg()."""
        if control_action == ControlAction.PRESET_UP:
            delta, self._msg_value = 1, self.midi_map.PRESET_UP_VAL
        else:
            delta, self._msg_value = -1, self.midi_map.PRESET_DOWN_VAL

        self._value += delta
        # Wrap around 1 and the maximum
        if self._value < 1:
            self._value = self.preset_num
        elif self._value > self.preset_num:
            self._value = 1

    def msg(self) -> ControlChange:
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=self.midi_map.PRESET_CC,
            value=self._msg_value,
        )

    def value(self) -> int:
        return self._value


class LooperManager:
    """State machine for the loop transport: record, play, overdub, and
    stop."""

    _EMPTY = 0
    _RECORDING = 1
    _PLAYING = 2
    _OVERDUBBING = 3
    _STOPPED = 4

    def __init__(self, midi_map: MidiMap, pattern_map: PatternMap):
        self.midi_map = midi_map
        self.pattern_map = pattern_map
        self.state = self._EMPTY
        self._msg_value = midi_map.LOOPER_UNDO_VAL

    def exec_action(self, control_action: ControlAction):
        """Advances the state machine. Retrieve the resulting message via
        msg()."""
        if control_action == ControlAction.LOOPER_REC_OD:
            if self.state in (self._EMPTY, self._STOPPED):
                self.state = self._RECORDING
            elif self.state == self._RECORDING:
                self.state = self._PLAYING
            elif self.state == self._PLAYING:
                self.state = self._OVERDUBBING
            elif self.state == self._OVERDUBBING:
                self.state = self._PLAYING
            self._msg_value = self.midi_map.LOOPER_RO_VAL

        elif control_action == ControlAction.LOOPER_STOP_PLAY:
            if self.state in (
                self._RECORDING,
                self._PLAYING,
                self._OVERDUBBING,
            ):
                self.state = self._STOPPED
            elif self.state == self._STOPPED:
                self.state = self._PLAYING
            self._msg_value = self.midi_map.LOOPER_SP_VAL

        elif control_action == ControlAction.LOOPER_CLEAR:
            self.state = self._EMPTY
            self._msg_value = self.midi_map.LOOPER_CLEAR_VAL

        else:  # ControlAction.LOOPER_UNDO -- does not change the transport state.
            self._msg_value = self.midi_map.LOOPER_UNDO_VAL

    def msg(self) -> ControlChange:
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=self.midi_map.LOOPER_CC,
            value=self._msg_value,
        )

    def pattern(self) -> Pattern:
        if self.state == self._RECORDING:
            return self.pattern_map.LOOPER_RECORDING
        if self.state == self._PLAYING:
            return self.pattern_map.LOOPER_PLAYING
        if self.state == self._OVERDUBBING:
            return self.pattern_map.LOOPER_OVERDUBBING
        if self.state == self._STOPPED:
            return self.pattern_map.LOOPER_STOPPED
        return self.pattern_map.LOOPER_EMPTY


class ValueParam:
    """A value target with a display label, MIDI CC number, and range."""

    def __init__(
        self,
        label: str,
        cc: int,
        min_value: int = 0,
        max_value: int = 100,
        step: int = 1,
        initial: int = 0,
        channel: int = None,
    ):
        """
        Args:
            label (str): Single character shown on the display, e.g. "V".
            cc (int): MIDI CC controller number.
            min_value (int, optional): Lower bound. Defaults to 0.
            max_value (int, optional): Upper bound. Defaults to 100.
            step (int, optional): Change per step. Defaults to 1.
            initial (int, optional): Starting value. Defaults to 0.
            channel (int, optional): MIDI channel override. Defaults to None.
        """
        self.label = label
        self.cc = _clamp_byte(cc)
        self.channel = _clamp_channel(channel)
        self.min_value = _clamp_byte(min_value)
        self.max_value = _clamp_byte(max_value)
        self.step = max(1, step)
        self.value = max(self.min_value, min(self.max_value, _clamp_byte(initial)))


class ValueManager:
    """Tracks a list of value targets and which one is currently
    selected."""

    def __init__(self, midi_map: MidiMap, params: list[ValueParam], hang_ms: int = 1000):
        """
        Args:
            midi_map (MidiMap): MIDI channel configuration.
            params (list[ValueParam]): Value targets to cycle through.
            hang_ms (int, optional): How long is_active() stays true after
                a change. Defaults to 1000.
        """
        if not params:
            raise ValueError("ValueManager needs at least one ValueParam")
        self.midi_map = midi_map
        self.params = params
        self.hang_ms = hang_ms
        self._index = 0
        self._last_change_ms = 0

    def exec_action(self, control_action: ControlAction):
        """Selects the next target, or adjusts the current target's value.
        Retrieve the resulting message via msg()."""
        if control_action == ControlAction.VALUE_TOGGLE:
            self._index = (self._index + 1) % len(self.params)
        else:
            param = self.params[self._index]
            delta = param.step if control_action == ControlAction.VALUE_UP else -param.step
            param.value = max(param.min_value, min(param.max_value, param.value + delta))

        self._last_change_ms = time.ticks_ms()

    def msg(self) -> ControlChange:
        param = self.params[self._index]
        return ControlChange(
            channel=param.channel if param.channel is not None else self.midi_map.CHANNEL,
            controller=param.cc,
            value=param.value,
        )

    def is_active(self) -> bool:
        """True if a value changed recently."""
        return time.ticks_diff(time.ticks_ms(), self._last_change_ms) < self.hang_ms

    def display_str(self) -> str:
        """Formatted display string, e.g. "V068"."""
        param = self.params[self._index]
        return "{}{:03d}".format(param.label, param.value)
