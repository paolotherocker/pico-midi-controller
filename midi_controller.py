from utils.neopixelmanager import NeoPixelManager, Pattern, Off
from utils.rotary import Rotary
from utils.midi import Message, ControlChange
from control_button import ControlButton, ControlAction, LEDMode
from tm1637 import TM1637
from collections import deque
import time

MIDI_INTERVAL_MS = 50


class MidiMap:
    CHANNEL: int
    SNAP_CC: int
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
        preset_cc: int,
        preset_up_val: int,
        preset_down_val: int,
        looper_cc: int = None,
        looper_ro_val: int = None,
        looper_sp_val: int = None,
        looper_undo_val: int = None,
        looper_clear_val: int = None,
    ):
        self.CHANNEL = channel
        self.SNAP_CC = snap_cc
        self.PRESET_CC = preset_cc
        self.PRESET_UP_VAL = preset_up_val
        self.PRESET_DOWN_VAL = preset_down_val
        self.LOOPER_CC = looper_cc
        self.LOOPER_RO_VAL = looper_ro_val
        self.LOOPER_SP_VAL = looper_sp_val
        self.LOOPER_UNDO_VAL = looper_undo_val
        self.LOOPER_CLEAR_VAL = looper_clear_val


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
    HOLD: Pattern

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
        hold: Pattern = Off(),
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
        self.HOLD = hold


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

    def exec_action(self, id: int, control_action: ControlAction):
        """Handle a SNAP_x_y press on button `id`. Retrieve the resulting
        MIDI message via msg()."""
        secondary = self._secondary.get(id, False)
        if self.active_id == id:
            secondary = not secondary
        self.active_id = id
        self._secondary[id] = secondary

        self._value = self._BASE_VALUE[control_action] + secondary

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
    button tagged LEDMode.LOOPER is driven from this one shared state
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


class MidiController:
    """Manages the control buttons, LEDs and the rotary encoder to generate MIDI messages"""

    _PATCH_MAP = [" ", "A", "B", "C", "D", "E", "F", "G", "H"]

    def __init__(
        self,
        control_buttons: list[ControlButton],
        np: NeoPixelManager,
        encoder: Rotary,
        display: TM1637,
        midi_map: MidiMap,
        preset_num: int = 8,
        pattern_map: PatternMap = PatternMap(),
    ):
        """Build Midi Controller object. Only pass pre-allocated and initialised objects

        Args:
            control_buttons (list[ControlButton]): list of ControlButton objects
            np (NeoPixelManager): Neo pixel array manager
            encoder (Rotary): Rotary encoder
            display (TM1637): TM1637 display manager
            midi_map (MidiMap): Midi map with pre-set values
            preset_num (int, optional): Maximum number of presets. Defaults to 8.
            pattern_map (PatternMap, optional): LED patterns for every mode
                (SNAP, LOOPER, HOLD). Defaults to all off.
        """
        self.control_buttons = control_buttons
        self.np = np
        self.encoder = encoder
        self.display = display
        self.midi_map = midi_map
        self.pattern_map = pattern_map

        # Manager instances are always created here, regardless of whether
        # the wiring/config actually uses them. Each one also builds its
        # own MIDI messages via msg(), so MidiController never touches raw
        # CC numbers.
        self.snap = SnapManager(midi_map=midi_map, pattern_map=pattern_map)
        self.preset = PresetManager(midi_map=midi_map, preset_num=preset_num)
        self.looper = LooperManager(midi_map=midi_map, pattern_map=pattern_map)

        self.msg_queue = deque((), 25)
        self.msg_time: int = 0

        self.display.brightness(3)
        self.display.show("")

    def _refresh_display(self):
        self.display.show(
            f" {self._PATCH_MAP[self.preset.value()]} {self.snap.value()}"
        )

    def _refresh_snap_leds(self):
        for idx, ctrl in enumerate(self.control_buttons):
            if ctrl.led_mode == LEDMode.SNAP:
                self.np.set_pattern(pattern=self.snap.pattern(idx), id=idx)

    def _refresh_looper_leds(self):
        pattern = self.looper.pattern()
        for idx, ctrl in enumerate(self.control_buttons):
            if ctrl.led_mode == LEDMode.LOOPER:
                self.np.set_pattern(pattern=pattern, id=idx)

    def update(self):
        for idx, ctrl in enumerate(self.control_buttons):
            action = ctrl.update()

            if action == ControlAction.NONE:
                continue

            if action in (
                ControlAction.SNAP_1_2,
                ControlAction.SNAP_3_4,
                ControlAction.SNAP_5_6,
                ControlAction.SNAP_7_8,
            ):
                self.snap.exec_action(idx, action)
                self.msg_queue.append(self.snap.msg())
                self._refresh_snap_leds()

            elif action in (ControlAction.PRESET_UP, ControlAction.PRESET_DOWN):
                self.preset.exec_action(action)
                self.msg_queue.append(self.preset.msg())
                self.msg_queue.append(self.snap.msg())

            elif action == ControlAction.HOLD:
                self.np.set_pattern(pattern=self.pattern_map.HOLD, id=idx)

            elif action in (
                ControlAction.LOOPER_REC_OD,
                ControlAction.LOOPER_STOP_PLAY,
                ControlAction.LOOPER_UNDO,
                ControlAction.LOOPER_CLEAR,
            ):
                self.looper.exec_action(action)
                self.msg_queue.append(self.looper.msg())
                self._refresh_looper_leds()

            self._refresh_display()

        self.np.poll()

        now = time.ticks_ms()
        if time.ticks_diff(now, self.msg_time) > MIDI_INTERVAL_MS:
            if len(self.msg_queue) > 0:
                self.msg_time = now
                msg: Message = self.msg_queue.popleft()
                print(*msg.to_bytes())
