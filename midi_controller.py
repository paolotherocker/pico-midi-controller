from utils.neopixelmanager import NeoPixelManager
from utils.rotary import Rotary
from utils.midimessages import Message, ControlChange
from control_button import ControlButton, ControlAction
from tm1637 import TM1637
from collections import deque
import time

MIDI_INTERVAL_MS = 200


class MidiMap:
    def __init__(
        self,
        channel: int,
        snap_cc: int,
        preset_cc: int,
        preset_up_val: int,
        preset_down_val: int,
    ):
        self.CHANNEL = channel
        self.SNAP_CC = snap_cc
        self.PRESET_CC = preset_cc
        self.PRESET_UP_VAL = preset_up_val
        self.PRESET_DOWN_VAL = preset_down_val


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
    ):
        self.control_buttons = control_buttons
        self.np = np
        self.encoder = encoder
        self.display = display
        self.preset_num = preset_num
        self.midi_map = midi_map

        self.preset: int = 1
        self.snap: int = 0
        self.msg_queue = deque((), 25)
        self.msg_time: int = 0

        self.display.brightness(3)
        self.display.show("")

    def _preset_update(self, delta: int):
        self.preset += delta

        # Wrap around 1 and the maximum
        if self.preset < 1:
            self.preset = self.preset_num
        elif self.preset > self.preset_num:
            self.preset = 1

    def refresh_display(self):
        buffer = " " + self._PATCH_MAP[self.preset] + " " + str(self.snap)
        self.display.show(buffer)

    def _snap_msg(self) -> ControlChange:
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=self.midi_map.SNAP_CC,
            value=self.snap,
        )

    def _preset_msg(self, value: int):
        return ControlChange(
            channel=self.midi_map.CHANNEL,
            controller=self.midi_map.PRESET_CC,
            value=value,
        )

    def update(self):
        action_id = -1
        action = ControlAction.NONE

        for ctrl in self.control_buttons:
            action_id = action_id + 1
            action = ctrl.update()

            if action in (
                ControlAction.SNAP_1_2,
                ControlAction.SNAP_3_4,
                ControlAction.SNAP_5_6,
                ControlAction.SNAP_7_8,
            ):
                self.np.set_pattern(pattern=ctrl.pattern(), id=ctrl.id)
                self.snap = ctrl.snap_value()

                self.msg_queue.append(self._snap_msg())

                for c_other in self.control_buttons:
                    if c_other.id != action_id:
                        c_other.set_passive()
                        self.np.set_pattern(pattern=c_other.pattern(), id=c_other.id)

            elif action == ControlAction.PRESET_UP:
                self._preset_update(1)
                self.msg_queue.append(self._preset_msg(self.midi_map.PRESET_UP_VAL))
                self.msg_queue.append(self._snap_msg())

            elif action == ControlAction.PRESET_DOWN:
                self._preset_update(-1)
                self.msg_queue.append(self._preset_msg(self.midi_map.PRESET_DOWN_VAL))
                self.msg_queue.append(self._snap_msg())

            if action != ControlAction.NONE:
                self.refresh_display()
                break

        self.np.poll()

        now = time.ticks_ms()
        if time.ticks_diff(now, self.msg_time) > MIDI_INTERVAL_MS:
            if len(self.msg_queue) > 0:
                self.msg_time = now
                msg: Message = self.msg_queue.popleft()
                print(*msg.to_bytes())
