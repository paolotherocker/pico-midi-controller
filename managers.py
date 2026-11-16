"""State managers for the MIDI controller: SNAP groups, presets, the
looper transport, stomps, and value targets. Also holds their shared
configuration types (MidiMap, PatternMap, ValueParam) and the
ConfigError codes surfaced by MidiController.
"""

import time
from utils.neopixelmanager import Pattern, Off
from utils.midi import Message, ControlChange
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


def _check_message(msg: Message, name: str) -> Message:
    """Return msg if it is a Message instance.

    Raises:
        TypeError: If msg is not a Message.
    """
    if not isinstance(msg, Message):
        raise TypeError("{} must be a Message: {!r}".format(name, msg))
    return msg


def _check_optional_message(msg: Message, name: str) -> Message:
    """Return msg if it is None or a Message instance.

    Raises:
        TypeError: If msg is neither None nor a Message.
    """
    if msg is None:
        return None
    return _check_message(msg, name)


class ConfigError:
    """Error codes shown on the display when MidiController detects a
    problem it can't safely continue from."""

    LED_MAP_SIZE = 1
    VALUE_RANGE = 2
    VALUE_UNCONFIGURED = 3
    QUEUE_OVERFLOW = 4
    STOMP_UNCONFIGURED = 5
    SNAP_DEFAULT = 6
    LOOPER_UNCONFIGURED = 7


class MidiMap:
    """The Message sent for each controller event. Any Message subclass
    may be used (e.g. ControlChange, ProgramChange); each carries its own
    channel. Looper messages are optional, and each stomp has an optional
    on and off message; unset entries default to None (unassigned)."""

    CHANNEL: int
    SNAP: tuple
    SNAP_MODE: Message
    PRESET_UP: Message
    PRESET_DOWN: Message
    PRESET_MODE: Message
    LOOPER_RO: Message
    LOOPER_SP: Message
    LOOPER_UNDO: Message
    LOOPER_CLEAR: Message
    STOMP_ON: tuple
    STOMP_OFF: tuple

    def __init__(
        self,
        channel: int,
        snap_1: Message,
        snap_2: Message,
        snap_3: Message,
        snap_4: Message,
        snap_5: Message,
        snap_6: Message,
        snap_7: Message,
        snap_8: Message,
        snap_mode: Message,
        preset_up: Message,
        preset_down: Message,
        preset_mode: Message,
        looper_ro: Message = None,
        looper_sp: Message = None,
        looper_undo: Message = None,
        looper_clear: Message = None,
        stomp_1_on: Message = None,
        stomp_1_off: Message = None,
        stomp_2_on: Message = None,
        stomp_2_off: Message = None,
        stomp_3_on: Message = None,
        stomp_3_off: Message = None,
        stomp_4_on: Message = None,
        stomp_4_off: Message = None,
    ):
        """
        Args:
            channel (int): Default MIDI channel (0-15) for value
                targets. Other entries use their own channel.
            snap_1 .. snap_8 (Message): Sent for each snap.
            snap_mode (Message): Sent before a snap when mode messages
                are enabled.
            preset_up, preset_down, preset_mode (Message): Sent for
                preset up, preset down and preset mode.
            looper_ro, looper_sp, looper_undo, looper_clear (Message,
                optional): Sent for record/overdub, stop/play, undo and
                clear.
            stomp_1_on .. stomp_4_on (Message, optional): Sent when the
                stomp is switched on.
            stomp_1_off .. stomp_4_off (Message, optional): Sent when
                the stomp is switched off.

        Raises:
            TypeError: If any entry is not a Message (or None for
                optional entries).
            ValueError: If only one of a stomp's on and off messages is
                given.
        """
        self.CHANNEL = _clamp_channel(channel)
        self.SNAP = (
            _check_message(snap_1, "snap_1"),
            _check_message(snap_2, "snap_2"),
            _check_message(snap_3, "snap_3"),
            _check_message(snap_4, "snap_4"),
            _check_message(snap_5, "snap_5"),
            _check_message(snap_6, "snap_6"),
            _check_message(snap_7, "snap_7"),
            _check_message(snap_8, "snap_8"),
        )
        self.SNAP_MODE = _check_message(snap_mode, "snap_mode")
        self.PRESET_UP = _check_message(preset_up, "preset_up")
        self.PRESET_DOWN = _check_message(preset_down, "preset_down")
        self.PRESET_MODE = _check_message(preset_mode, "preset_mode")
        self.LOOPER_RO = _check_optional_message(looper_ro, "looper_ro")
        self.LOOPER_SP = _check_optional_message(looper_sp, "looper_sp")
        self.LOOPER_UNDO = _check_optional_message(looper_undo, "looper_undo")
        self.LOOPER_CLEAR = _check_optional_message(looper_clear, "looper_clear")

        stomp_on = (stomp_1_on, stomp_2_on, stomp_3_on, stomp_4_on)
        stomp_off = (stomp_1_off, stomp_2_off, stomp_3_off, stomp_4_off)
        for index in range(4):
            name = "stomp_{}".format(index + 1)
            _check_optional_message(stomp_on[index], name + "_on")
            _check_optional_message(stomp_off[index], name + "_off")
            if (stomp_on[index] is None) != (stomp_off[index] is None):
                raise ValueError(
                    "{} needs both an on and an off message".format(name)
                )
        self.STOMP_ON = stomp_on
        self.STOMP_OFF = stomp_off


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

    # Group actions in ascending snap order; group index = (snap - 1) // 2.
    _GROUP_ACTIONS = (
        ControlAction.SNAP_1_2,
        ControlAction.SNAP_3_4,
        ControlAction.SNAP_5_6,
        ControlAction.SNAP_7_8,
    )

    _ACTION_BY_LED_MODE = {
        LEDMode.SNAP_1_2: ControlAction.SNAP_1_2,
        LEDMode.SNAP_3_4: ControlAction.SNAP_3_4,
        LEDMode.SNAP_5_6: ControlAction.SNAP_5_6,
        LEDMode.SNAP_7_8: ControlAction.SNAP_7_8,
    }

    def __init__(
        self, midi_map: MidiMap, pattern_map: PatternMap, default_snap: int = 1
    ):
        """
        Args:
            midi_map (MidiMap): MIDI message configuration.
            pattern_map (PatternMap): LED patterns to use.
            default_snap (int, optional): Snap (1-8) selected at start-up
                and by reset(). Defaults to 1.

        Raises:
            ValueError: If default_snap is not an integer from 1 to 8.
        """
        if not isinstance(default_snap, int) or not 1 <= default_snap <= 8:
            raise ValueError("default_snap must be 1-8: {!r}".format(default_snap))

        self.midi_map = midi_map
        self.pattern_map = pattern_map
        self._default_snap = default_snap

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

        # Starts on the default snap, no other secondary values set.
        self.reset()

    def reset(self):
        """Clears every group's secondary value and reselects the default
        snap. Called on start-up and whenever a preset command is
        received, since a preset shouldn't inherit whatever SNAP state
        was active on the previous preset."""
        action = self._GROUP_ACTIONS[(self._default_snap - 1) // 2]
        self._secondary = {action: self._default_snap % 2 == 0}
        self.active_action = action
        self._value = self._default_snap

    def exec_action(self, control_action: ControlAction):
        """Updates state for a SNAP press. Retrieve the resulting message
        via msg()."""
        secondary = self._secondary.get(control_action, False)
        if self.active_action == control_action:
            secondary = not secondary
        self.active_action = control_action
        self._secondary[control_action] = secondary

        self._value = self._BASE_VALUE[control_action] + secondary

    def snap_mode_msg(self) -> Message:
        return self.midi_map.SNAP_MODE

    def msg(self) -> Message:
        return self.midi_map.SNAP[self._value - 1]

    def value(self) -> int:
        return self._value

    def display_str(self) -> str:
        """"Sn" followed by a space and the snap number, e.g. "Sn 3"."""
        return "Sn {}".format(self._value)

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
        self._msg = midi_map.PRESET_UP

    def preset_mode_msg(self) -> Message:
        return self.midi_map.PRESET_MODE

    def exec_action(self, control_action: ControlAction):
        """Updates the preset number. Retrieve the resulting message via
        msg()."""
        if control_action == ControlAction.PRESET_UP:
            delta, self._msg = 1, self.midi_map.PRESET_UP
        else:
            delta, self._msg = -1, self.midi_map.PRESET_DOWN

        self._value += delta
        # Wrap around 1 and the maximum
        if self._value < 1:
            self._value = self.preset_num
        elif self._value > self.preset_num:
            self._value = 1

    def msg(self) -> Message:
        return self._msg

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
        self._msg = midi_map.LOOPER_UNDO
        self._text = self._TXT_STOP

    def _message_for(self, control_action: ControlAction) -> Message:
        """MidiMap message for a looper action, or None if unassigned."""
        if control_action == ControlAction.LOOPER_REC_OD:
            return self.midi_map.LOOPER_RO
        if control_action == ControlAction.LOOPER_STOP_PLAY:
            return self.midi_map.LOOPER_SP
        if control_action == ControlAction.LOOPER_CLEAR:
            return self.midi_map.LOOPER_CLEAR
        if control_action == ControlAction.LOOPER_UNDO:
            return self.midi_map.LOOPER_UNDO
        raise ValueError("not a looper action: {!r}".format(control_action))

    def is_assigned(self, control_action: ControlAction) -> bool:
        """True if the looper action has a message in the MidiMap.

        Raises:
            ValueError: If control_action is not a looper action.
        """
        return self._message_for(control_action) is not None

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
            self._msg = self.midi_map.LOOPER_RO
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
            self._msg = self.midi_map.LOOPER_SP
            self._text = (
                self._TXT_PLAY if self.state == self._PLAYING else self._TXT_STOP
            )

        elif control_action == ControlAction.LOOPER_CLEAR:
            self.state = self._EMPTY
            self._msg = self.midi_map.LOOPER_CLEAR
            self._text = self._TXT_CLEAR

        else:  # ControlAction.LOOPER_UNDO -- does not change the transport state.
            self._msg = self.midi_map.LOOPER_UNDO
            self._text = self._TXT_UNDO

    def msg(self) -> Message:
        """Message for the most recent looper action.

        Raises:
            ValueError: If that action has no message assigned.
        """
        if self._msg is None:
            raise ValueError("looper action has no message assigned")
        return self._msg

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
    sends its on or off message."""

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

    def is_assigned(self, control_action: ControlAction) -> bool:
        """True if the stomp has on and off messages in the MidiMap.

        Raises:
            ValueError: If control_action is not a stomp action.
        """
        return self.midi_map.STOMP_ON[self._index(control_action)] is not None

    def is_on(self, control_action: ControlAction) -> bool:
        """True if the stomp is on.

        Raises:
            ValueError: If control_action is not a stomp action.
        """
        return self._states[self._index(control_action)]

    def msg(self) -> Message:
        """On or off message for the most recently toggled stomp.

        Raises:
            ValueError: If that stomp has no messages assigned.
        """
        if self._states[self._last]:
            msg = self.midi_map.STOMP_ON[self._last]
        else:
            msg = self.midi_map.STOMP_OFF[self._last]
        if msg is None:
            raise ValueError("stomp {} has no message assigned".format(self._last + 1))
        return msg

    def display_str(self) -> str:
        """"t", the stomp number, a space and the state (1 on, 0 off),
        e.g. "t2 1"."""
        return "t{} {}".format(self._last + 1, int(self._states[self._last]))

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
