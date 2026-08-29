from utils.neopixelmanager import NeoPixelManager, Pattern, Off
from utils.midi import Message, ControlChange
from control_hardware import (
    Control,
    ControlButton,
    ControlEncoder,
    ControlAction,
    LEDMode,
)
from tm1637 import TM1637
from collections import deque
import time

MIDI_INTERVAL_MS = 8


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
        looper_cc: int = None,
        looper_ro_val: int = None,
        looper_sp_val: int = None,
        looper_undo_val: int = None,
        looper_clear_val: int = None,
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
    """All NeoPixel patterns used across LED modes, in one place -- the
    LED-side counterpart to MidiMap. Any pattern left unset stays off."""

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
    """Shared state for the four SNAP_x_y button groups.

    Only one group is ever "active" (bright) at a time; pressing the
    already-active group toggles its own secondary value (e.g. 1 <-> 2).
    Each group remembers its own secondary value even while passive
    (dimmed), so its dimmed LED still shows which of its two values was
    last selected.
    """

    _BASE_VALUE = {
        ControlAction.SNAP_1_2: 1,
        ControlAction.SNAP_3_4: 3,
        ControlAction.SNAP_5_6: 5,
        ControlAction.SNAP_7_8: 7,
    }

    def __init__(self, midi_map: MidiMap, pattern_map: PatternMap):
        self.midi_map = midi_map
        self.pattern_map = pattern_map
        self.active_id = None
        self._secondary = {}
        self._value = 0

        self._snap_mode_msg = ControlChange(
            channel=midi_map.CHANNEL,
            controller=midi_map.SNAP_CC,
            value=midi_map.SNAP_MODE_VAL,
        )

    def exec_action(self, id: int, control_action: ControlAction):
        """Handle a SNAP_x_y press on button `id`. Retrieve the resulting
        MIDI message via msg()."""
        secondary = self._secondary.get(id, False)
        if self.active_id == id:
            secondary = not secondary
        self.active_id = id
        self._secondary[id] = secondary

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

    def pattern(self, id: int) -> Pattern:
        secondary = self._secondary.get(id, False)
        if id == self.active_id:
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
        self.preset_num = preset_num
        self._value = initial
        self._msg_value = midi_map.PRESET_UP_VAL

    def exec_action(self, control_action: ControlAction):
        """Handle a PRESET_UP/PRESET_DOWN action. Retrieve the resulting
        MIDI message via msg()."""
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
    """Shared loop-transport state machine.

    LOOPER_REC_OD, LOOPER_STOP_PLAY, LOOPER_UNDO and LOOPER_CLEAR are typically wired to separate
    physical footswitches, but they all act on the same loop, so every
    entry tagged LEDMode.LOOPER is driven from this one shared state
    rather than each switch tracking its own local flag.
    """

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
        """Advance the state machine. Retrieve the resulting MIDI message
        via msg()."""
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
    """One assignable value target: display label, MIDI CC destination
    and value range."""

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
            cc (int): MIDI CC controller number to send.
            min_value (int, optional): Lower bound. Defaults to 0.
            max_value (int, optional): Upper bound. Defaults to 100.
            step (int, optional): Change per VALUE_UP/VALUE_DOWN. Defaults to 1.
            initial (int, optional): Starting value. Defaults to 0.
            channel (int, optional): Overrides ValueManager's default
                channel for this param if set. Defaults to None.
        """
        self.label = label
        self.cc = _clamp_byte(cc)
        self.channel = _clamp_channel(channel)
        self.min_value = _clamp_byte(min_value)
        self.max_value = _clamp_byte(max_value)
        self.step = max(1, step)
        self.value = max(self.min_value, min(self.max_value, _clamp_byte(initial)))


class ValueManager:
    """Owns the values of one or more ValueParam targets and which one is
    currently selected.

    exec_action() handles VALUE_TOGGLE (cycle to the next target) and
    VALUE_UP/VALUE_DOWN (adjust the current target's value), from any
    control hardware that reports those ControlActions -- an encoder for
    up/down, a button for toggle, or otherwise. msg() retrieves the
    resulting MIDI message. is_active() reports whether a change
    happened recently, for the caller to decide what the display shows.
    """

    def __init__(
        self, midi_map: MidiMap, params: list[ValueParam], hang_ms: int = 1000
    ):
        if not params:
            raise ValueError("ValueManager needs at least one ValueParam")
        self.midi_map = midi_map
        self.params = params
        self.hang_ms = hang_ms
        self._index = 0
        self._last_change_ms = 0

    def exec_action(self, control_action: ControlAction):
        """Handle a VALUE_TOGGLE/VALUE_UP/VALUE_DOWN action. Retrieve the
        resulting MIDI message via msg()."""
        if control_action == ControlAction.VALUE_TOGGLE:
            self._index = (self._index + 1) % len(self.params)
        else:
            param = self.params[self._index]
            delta = (
                param.step if control_action == ControlAction.VALUE_UP else -param.step
            )
            param.value = max(
                param.min_value, min(param.max_value, param.value + delta)
            )

        self._last_change_ms = time.ticks_ms()

    def msg(self) -> ControlChange:
        param = self.params[self._index]
        return ControlChange(
            channel=(
                param.channel if param.channel is not None else self.midi_map.CHANNEL
            ),
            controller=param.cc,
            value=param.value,
        )

    def is_active(self) -> bool:
        return time.ticks_diff(time.ticks_ms(), self._last_change_ms) < self.hang_ms

    def display_str(self) -> str:
        """Formatted "<label><value>" string, e.g. "V068"."""
        param = self.params[self._index]
        return "{}{:03d}".format(param.label, param.value)


class MidiController:
    """Manages the control buttons, LEDs, display and rotary encoder to
    generate MIDI messages"""

    _PATCH_MAP = [" ", "A", "B", "C", "D", "E", "F", "G", "H"]

    # Converts an led_map entry into the SnapManager id it corresponds to,
    # so led_map can list SNAP_1_2/SNAP_3_4/etc in any order regardless of
    # which control_buttons id actually drives each group.
    _SNAP_MODE_TO_ID = {
        LEDMode.SNAP_1_2: 0,
        LEDMode.SNAP_3_4: 1,
        LEDMode.SNAP_5_6: 2,
        LEDMode.SNAP_7_8: 3,
    }

    def __init__(
        self,
        control_buttons: list[ControlButton],
        np: NeoPixelManager,
        display: TM1637,
        midi_map: MidiMap,
        preset_num: int = 8,
        pattern_map: PatternMap = PatternMap(),
        send_mode_msg: bool = False,
        remember_snap: bool = False,
        led_map: list[LEDMode] = None,
        control_encoder: ControlEncoder = None,
        value_params: list[ValueParam] = None,
        value_hang_ms: int = 1000,
    ):
        """Build Midi Controller object. Only pass pre-allocated and initialised objects

        Args:
            control_buttons (list[ControlButton]): every physical button --
                footswitches, standalone menu buttons, an encoder's switch, etc.
                A footswitch driving SNAP_1_2/3_4/5_6/7_8 must use the id from
                _SNAP_MODE_TO_ID (0/1/2/3) matching that group.
            np (NeoPixelManager): Neo pixel array manager
            display (TM1637): TM1637 display manager
            midi_map (MidiMap): Midi map with pre-set values
            preset_num (int, optional): Maximum number of presets. Defaults to 8.
            pattern_map (PatternMap, optional): LED patterns for every mode
                (SNAP, LOOPER). Defaults to all off.
            send_mode_msg (bool): Send a snap mode msg to switch to snap mode every
                time a snap message is being sent
            remember_snap (bool): Sends a snap message every time a preset msg is
                sent, to make sure the device switches to the same snap number
            led_map (list[LEDMode], optional): One entry per NeoPixel group, in NP
                index order. SNAP_1_2/SNAP_3_4/SNAP_5_6/SNAP_7_8 can appear in any
                order -- converted to the matching SnapManager id internally.
                Fully decoupled from control_buttons.
            control_encoder (ControlEncoder, optional): Rotary encoder reporting
                VALUE_UP/VALUE_DOWN. Defaults to None.
            value_params (list[ValueParam], optional): Assignable CC targets,
                cycled by VALUE_TOGGLE. Required if control_encoder or any
                control_button reports VALUE_UP/VALUE_DOWN/VALUE_TOGGLE.
            value_hang_ms (int, optional): How long the value display stays up
                after the last change. Defaults to 1000.
        """
        self.np = np
        self.display = display
        self.pattern_map = pattern_map
        self.send_mode_msg = send_mode_msg
        self.remember_snap = remember_snap
        self.led_map = led_map or []

        self.value = (
            ValueManager(midi_map=midi_map, params=value_params, hang_ms=value_hang_ms)
            if value_params is not None
            else None
        )

        # Manager instances
        self.snap = SnapManager(midi_map=midi_map, pattern_map=pattern_map)
        self.preset = PresetManager(midi_map=midi_map, preset_num=preset_num)
        self.looper = LooperManager(midi_map=midi_map, pattern_map=pattern_map)

        # Every piece of control hardware (all Control subclasses), polled
        # uniformly in update()
        self._hardware: list[Control] = list(control_buttons)
        if control_encoder is not None:
            self._hardware.append(control_encoder)

        # MIDI message queue
        self.msg_queue = deque((), 25)
        self.msg_time: int = 0

        self.display.brightness(3)
        self.display.show("")

    def _handle_action(self, id: int, action: ControlAction):
        """Single dispatch point for every ControlAction, regardless of
        which control hardware produced it."""
        if action == ControlAction.NONE:
            return

        if action in (
            ControlAction.SNAP_1_2,
            ControlAction.SNAP_3_4,
            ControlAction.SNAP_5_6,
            ControlAction.SNAP_7_8,
        ):
            self.snap.exec_action(id, action)
            if self.send_mode_msg == True:
                self.msg_queue.append(self.snap.snap_mode_msg())
            self.msg_queue.append(self.snap.msg())

        elif action in (ControlAction.PRESET_UP, ControlAction.PRESET_DOWN):
            self.preset.exec_action(action)
            self.msg_queue.append(self.preset.msg())
            if self.remember_snap == True:
                self.msg_queue.append(self.snap.msg())

        elif action in (
            ControlAction.LOOPER_REC_OD,
            ControlAction.LOOPER_STOP_PLAY,
            ControlAction.LOOPER_UNDO,
            ControlAction.LOOPER_CLEAR,
        ):
            self.looper.exec_action(action)
            self.msg_queue.append(self.looper.msg())

        elif action in (
            ControlAction.VALUE_UP,
            ControlAction.VALUE_DOWN,
            ControlAction.VALUE_TOGGLE,
        ):
            if self.value:
                self.value.exec_action(action)
                self.msg_queue.append(self.value.msg())

    def update(self):
        for ctrl in self._hardware:
            self._handle_action(ctrl.id(), ctrl.update())

        # Refresh NP -- driven entirely by led_map, never by control_buttons.
        # led_mode is converted to the matching SnapManager id via the table.
        for np_id, led_mode in enumerate(self.led_map):
            snap_id = self._SNAP_MODE_TO_ID.get(led_mode)
            if snap_id is not None:
                self.np.set_pattern(pattern=self.snap.pattern(snap_id), id=np_id)
            elif led_mode == LEDMode.LOOPER:
                self.np.set_pattern(pattern=self.looper.pattern(), id=np_id)

        # Refresh Display -- encoder value overrides preset/snap while active
        if self.value and self.value.is_active():
            self.display.show(self.value.display_str())
        else:
            self.display.show(
                f" {self._PATCH_MAP[self.preset.value()]} {self.snap.value()}"
            )

        self.np.poll()

        now = time.ticks_ms()
        if time.ticks_diff(now, self.msg_time) > MIDI_INTERVAL_MS:
            if len(self.msg_queue) > 0:
                self.msg_time = now
                msg: Message = self.msg_queue.popleft()
                print(*msg.to_bytes())
