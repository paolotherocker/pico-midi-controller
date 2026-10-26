"""State managers for the MIDI controller: SNAP groups, presets, the
looper transport, stomps, and value targets. Also holds their shared
configuration types (MidiMap, PatternMap, ValueParam) and the
ConfigError codes surfaced by MidiController.
"""

import time
from utils.neopixelmanager import Pattern, Off
from utils.midi import ControlChange
from control_hardware import ControlAction, LEDMode


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
    STOMP_UNCONFIGURED = 5


class MidiMap:
    """MIDI channel, CC numbers and message values. The stomp CCs are
    optional and default to None (unassigned)."""

    CHANNEL: int
    SNAP_CC: int
    SNAP_MODE_VAL: int
    PRESET_CC: int
    PRESET_UP_VAL: int
    PRESET_DOWN_VAL: int
    PRESET_MODE_VAL: int
    LOOPER_CC: int
    LOOPER_RO_VAL: int
    LOOPER_SP_VAL: int
    LOOPER_UNDO_VAL: int
    LOOPER_CLEAR_VAL: int
    STOMP_1_CC: int
    STOMP_2_CC: int
    STOMP_3_CC: int
    STOMP_4_CC: int

    def __init__(
        self,
        channel: int,
        snap_cc: int,
        snap_mode_val: int,
        preset_cc: int,
        preset_up_val: int,
        preset_down_val: int,
        preset_mode_val: int,
        looper_cc: int,
        looper_ro_val: int,
        looper_sp_val: int,
        looper_undo_val: int,
        looper_clear_val: int,
        stomp_1_cc: int = None,
        stomp_2_cc: int = None,
        stomp_3_cc: int = None,
        stomp_4_cc: int = None,
    ):
        self.CHANNEL = _clamp_channel(channel)
        self.SNAP_CC = _clamp_byte(snap_cc)
        self.SNAP_MODE_VAL = _clamp_byte(snap_mode_val)
        self.PRESET_CC = _clamp_byte(preset_cc)
        self.PRESET_UP_VAL = _clamp_byte(preset_up_val)
        self.PRESET_DOWN_VAL = _clamp_byte(preset_down_val)
        self.PRESET_MODE_VAL = _clamp_byte(preset_mode_val)
        self.LOOPER_CC = _clamp_byte(looper_cc)
        self.LOOPER_RO_VAL = _clamp_byte(looper_ro_val)
        self.LOOPER_SP_VAL = _clamp_byte(looper_sp_val)
        self.LOOPER_UNDO_VAL = _clamp_byte(looper_undo_val)
        self.LOOPER_CLEAR_VAL = _clamp_byte(looper_clear_val)
        self.STOMP_1_CC = _clamp_byte(stomp_1_cc)
        self.STOMP_2_CC = _clamp_byte(stomp_2_cc)
        self.STOMP_3_CC = _clamp_byte(stomp_3_cc)
        self.STOMP_4_CC = _clamp_byte(stomp_4_cc)


class PatternMap:
    """NeoPixel patterns for each LED state. Unset patterns stay off.
    Each snap (1-8) has its own active pattern; passive groups share
    one pattern. Each stomp (1-4) has a pattern for when it is on."""

    SNAP_ACTIVE_1: Pattern
    SNAP_ACTIVE_2: Pattern
    SNAP_ACTIVE_3: Pattern
    SNAP_ACTIVE_4: Pattern
    SNAP_ACTIVE_5: Pattern
    SNAP_ACTIVE_6: Pattern
    SNAP_ACTIVE_7: Pattern
    SNAP_ACTIVE_8: Pattern
    SNAP_PASSIVE: Pattern
    LOOPER_EMPTY: Pattern
    LOOPER_RECORDING: Pattern
    LOOPER_PLAYING: Pattern
    LOOPER_OVERDUBBING: Pattern
    LOOPER_STOPPED: Pattern
    STOMP_1: Pattern
    STOMP_2: Pattern
    STOMP_3: Pattern
    STOMP_4: Pattern

    def __init__(
        self,
        snap_active_1: Pattern = Off(),
        snap_active_2: Pattern = Off(),
        snap_active_3: Pattern = Off(),
        snap_active_4: Pattern = Off(),
        snap_active_5: Pattern = Off(),
        snap_active_6: Pattern = Off(),
        snap_active_7: Pattern = Off(),
        snap_active_8: Pattern = Off(),
        snap_passive: Pattern = Off(),
        looper_empty: Pattern = Off(),
        looper_recording: Pattern = Off(),
        looper_playing: Pattern = Off(),
        looper_overdubbing: Pattern = Off(),
        looper_stopped: Pattern = Off(),
        stomp_1: Pattern = Off(),
        stomp_2: Pattern = Off(),
        stomp_3: Pattern = Off(),
        stomp_4: Pattern = Off(),
    ):
        self.SNAP_ACTIVE_1 = snap_active_1
        self.SNAP_ACTIVE_2 = snap_active_2
        self.SNAP_ACTIVE_3 = snap_active_3
        self.SNAP_ACTIVE_4 = snap_active_4
        self.SNAP_ACTIVE_5 = snap_active_5
        self.SNAP_ACTIVE_6 = snap_active_6
        self.SNAP_ACTIVE_7 = snap_active_7
        self.SNAP_ACTIVE_8 = snap_active_8
        self.SNAP_PASSIVE = snap_passive
        self.LOOPER_EMPTY = looper_empty
        self.LOOPER_RECORDING = looper_recording
        self.LOOPER_PLAYING = looper_playing
        self.LOOPER_OVERDUBBING = looper_overdubbing
        self.LOOPER_STOPPED = looper_stopped
        self.STOMP_1 = stomp_1
        self.STOMP_2 = stomp_2
        self.STOMP_3 = stomp_3
        self.STOMP_4 = stomp_4


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

        self._snap_mode_msg = ControlChange(
            channel=midi_map.CHANNEL,
            controller=midi_map.SNAP_CC,
            value=midi_map.SNAP_MODE_VAL,
        )

        # Active pattern for each snap, indexed by snap number - 1.
        self._active_patterns = (
            pattern_map.SNAP_ACTIVE_1,
            pattern_map.SNAP_ACTIVE_2,
            pattern_map.SNAP_ACTIVE_3,
            pattern_map.SNAP_ACTIVE_4,
            pattern_map.SNAP_ACTIVE_5,
            pattern_map.SNAP_ACTIVE_6,
            pattern_map.SNAP_ACTIVE_7,
            pattern_map.SNAP_ACTIVE_8,
        )

        # Starts on SNAP 1/2 active, no secondary values set.
        self.reset()

    def reset(self):
        """Clears every group's secondary value and reactivates SNAP 1/2,
        the default group. Called on start-up and whenever a preset
        command is received, since a preset shouldn't inherit whatever
        SNAP state was active on the previous preset."""
        self._secondary = {}
        self.active_action = ControlAction.SNAP_1_2
        self._value = self._BASE_VALUE[ControlAction.SNAP_1_2]

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

    def display_str(self) -> str:
        """"S" in the second position and the snap number in the last,
        e.g. " S 3"."""
        return " S{:>2d}".format(self._value)

    def pattern(self, led_mode: LEDMode) -> Pattern:
        """LED pattern for a SNAP group: the active snap's own pattern
        for the active group, the shared passive pattern otherwise."""
        control_action = self._ACTION_BY_LED_MODE[led_mode]
        if control_action == self.active_action:
            return self._active_patterns[self._value - 1]
        return self.pattern_map.SNAP_PASSIVE


class PresetManager:
    """Owns the current preset number and its wraparound logic."""

    def __init__(self, midi_map: MidiMap, preset_num: int = 8, initial: int = 1):
        self.midi_map = midi_map
        self.preset_num = max(1, preset_num)
        self._value = max(1, min(self.preset_num, initial))
        self._msg_value = midi_map.PRESET_UP_VAL

        self._preset_mode_msg = ControlChange(
            channel=midi_map.CHANNEL,
            controller=midi_map.PRESET_CC,
            value=midi_map.PRESET_MODE_VAL,
        )

    def preset_mode_msg(self):
        return self._preset_mode_msg

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

    def display_str(self) -> str:
        """"P" in the second position and the preset number in the last,
        e.g. " P 1" or " P12"."""
        return " P{:>2d}".format(self._value)


class LooperManager:
    """State machine for the loop transport: record, play, overdub, and
    stop."""

    _EMPTY = 0
    _RECORDING = 1
    _PLAYING = 2
    _OVERDUBBING = 3
    _STOPPED = 4

    # Four-character, 7-segment friendly labels.
    _TXT_REC = "rEC "
    _TXT_PLAY = "PLAY"
    _TXT_OVERDUB = "OdUb"
    _TXT_STOP = "StOP"
    _TXT_CLEAR = "CLr "
    _TXT_UNDO = "UndO"

    def __init__(self, midi_map: MidiMap, pattern_map: PatternMap):
        self.midi_map = midi_map
        self.pattern_map = pattern_map
        self.state = self._EMPTY
        self._msg_value = midi_map.LOOPER_UNDO_VAL
        self._text = self._TXT_STOP

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
            if self.state == self._RECORDING:
                self._text = self._TXT_REC
            elif self.state == self._OVERDUBBING:
                self._text = self._TXT_OVERDUB
            else:
                self._text = self._TXT_PLAY

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
            self._text = (
                self._TXT_PLAY if self.state == self._PLAYING else self._TXT_STOP
            )

        elif control_action == ControlAction.LOOPER_CLEAR:
            self.state = self._EMPTY
            self._msg_value = self.midi_map.LOOPER_CLEAR_VAL
            self._text = self._TXT_CLEAR

        else:  # ControlAction.LOOPER_UNDO -- does not change the transport state.
            self._msg_value = self.midi_map.LOOPER_UNDO_VAL
            self._text = self._TXT_UNDO

    def msg(self) -> ControlChange:
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=self.midi_map.LOOPER_CC,
            value=self._msg_value,
        )

    def display_str(self) -> str:
        """Label for the latest loop command: "rEC ", "PLAY", "OdUb",
        "StOP", "CLr " or "UndO". Shows the resulting state for record
        and stop/play."""
        return self._text

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


class StompManager:
    """Four independent on/off stomps. Each press toggles one stomp and
    sends its state as a CC value (127 on, 0 off)."""

    ON_VALUE = 127
    OFF_VALUE = 0

    _ACTIONS = (
        ControlAction.STOMP_1,
        ControlAction.STOMP_2,
        ControlAction.STOMP_3,
        ControlAction.STOMP_4,
    )

    _ACTION_BY_LED_MODE = {
        LEDMode.STOMP_1: ControlAction.STOMP_1,
        LEDMode.STOMP_2: ControlAction.STOMP_2,
        LEDMode.STOMP_3: ControlAction.STOMP_3,
        LEDMode.STOMP_4: ControlAction.STOMP_4,
    }

    # Shared instance so MidiController's identity check sees no change
    # between consecutive inactive frames.
    _OFF = Off()

    def __init__(self, midi_map: MidiMap, pattern_map: PatternMap):
        self.midi_map = midi_map
        self.pattern_map = pattern_map

        self._ccs = (
            midi_map.STOMP_1_CC,
            midi_map.STOMP_2_CC,
            midi_map.STOMP_3_CC,
            midi_map.STOMP_4_CC,
        )
        self._active_patterns = (
            pattern_map.STOMP_1,
            pattern_map.STOMP_2,
            pattern_map.STOMP_3,
            pattern_map.STOMP_4,
        )
        self._states = [False, False, False, False]
        self._last = 0

    def _index(self, control_action: ControlAction) -> int:
        index = control_action - ControlAction.STOMP_1
        if not 0 <= index < len(self._ACTIONS):
            raise ValueError("not a stomp action: {!r}".format(control_action))
        return index

    def exec_action(self, control_action: ControlAction):
        """Toggles a stomp. Retrieve the resulting message via msg().

        Raises:
            ValueError: If control_action is not a stomp action.
        """
        index = self._index(control_action)
        self._states[index] = not self._states[index]
        self._last = index

    def cc(self, control_action: ControlAction) -> int:
        """CC number assigned to a stomp, or None if unassigned.

        Raises:
            ValueError: If control_action is not a stomp action.
        """
        return self._ccs[self._index(control_action)]

    def is_on(self, control_action: ControlAction) -> bool:
        """True if the stomp is on.

        Raises:
            ValueError: If control_action is not a stomp action.
        """
        return self._states[self._index(control_action)]

    def msg(self) -> ControlChange:
        """CC message for the most recently toggled stomp.

        Raises:
            ValueError: If that stomp has no CC assigned.
        """
        cc = self._ccs[self._last]
        if cc is None:
            raise ValueError("stomp {} has no CC assigned".format(self._last + 1))
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=cc,
            value=self.ON_VALUE if self._states[self._last] else self.OFF_VALUE,
        )

    def display_str(self) -> str:
        """Stomp number and state of the latest toggle, e.g. "t1On" or
        "t3OF"."""
        return "t{}{}".format(
            self._last + 1, "On" if self._states[self._last] else "OF"
        )

    def pattern(self, led_mode: LEDMode) -> Pattern:
        """LED pattern for a stomp: its own pattern while on, off
        otherwise."""
        index = self._index(self._ACTION_BY_LED_MODE[led_mode])
        if self._states[index]:
            return self._active_patterns[index]
        return self._OFF


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

    # Encoder acceleration: consecutive steps arriving within these
    # intervals get a larger multiplier applied to param.step.
    _ACCEL_FAST_MS = 40
    _ACCEL_FAST_MULT = 4
    _ACCEL_MED_MS = 80
    _ACCEL_MED_MULT = 2

    def __init__(self, midi_map: MidiMap, params: list[ValueParam]):
        """
        Args:
            midi_map (MidiMap): MIDI channel configuration.
            params (list[ValueParam]): Value targets to cycle through.

        Raises:
            ValueError: If params is empty.
        """
        if not params:
            raise ValueError("ValueManager needs at least one ValueParam")
        self.midi_map = midi_map
        self.params = params
        self._index = 0
        self._last_step_ms = 0

    def exec_action(self, control_action: ControlAction):
        """Selects the next target, or adjusts the current target's value.
        Retrieve the resulting message via msg()."""
        if control_action == ControlAction.VALUE_DISP:
            # do nothing
            pass
        elif control_action == ControlAction.VALUE_TOGGLE:
            self._index = (self._index + 1) % len(self.params)
        elif control_action in (ControlAction.VALUE_UP, ControlAction.VALUE_DOWN):
            param = self.params[self._index]

            now = time.ticks_ms()
            interval = time.ticks_diff(now, self._last_step_ms)
            self._last_step_ms = now
            if interval < self._ACCEL_FAST_MS:
                mult = self._ACCEL_FAST_MULT
            elif interval < self._ACCEL_MED_MS:
                mult = self._ACCEL_MED_MULT
            else:
                mult = 1

            delta = param.step * mult
            if control_action == ControlAction.VALUE_DOWN:
                delta = -delta
            param.value = max(
                param.min_value, min(param.max_value, param.value + delta)
            )

    def msg(self) -> ControlChange:
        param = self.params[self._index]
        return ControlChange(
            channel=(
                param.channel if param.channel is not None else self.midi_map.CHANNEL
            ),
            controller=param.cc,
            value=param.value,
        )

    def display_str(self) -> str:
        """Formatted display string, e.g. "V068"."""
        param = self.params[self._index]
        return "{}{:3d}".format(param.label, param.value)
