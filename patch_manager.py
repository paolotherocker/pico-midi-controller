from utils.neopixelmanager import NeoPixelManager, Pulse, Solid
from utils.rotary import Rotary, RotaryEvent
from control_button import ControlButton, ControlAction
from tm1637 import TM1637


class PatchManager:
    """Manages the control buttons, LEDs and the rotary encoder to generate MIDI messages"""

    _PATCH_MAP = [" ", "A", "B", "C", "D", "E", "F", "G", "H"]

    def __init__(
        self,
        control_buttons: list[ControlButton],
        np: NeoPixelManager,
        encoder: Rotary,
        display: TM1637,
        preset_num: int = 8,
    ):
        self.control_buttons = control_buttons
        self.np = np
        self.encoder = encoder
        self.display = display
        self.preset_num = preset_num

        self.preset: int = 1
        self.snap: int = 0

        self.display.brightness(3)
        self.display.show("")

    def preset_update(self, delta: int):
        self.preset += delta

        # Wrap around 1 and the maximum
        if self.preset < 1:
            self.preset = self.preset_num
        elif self.preset > self.preset_num:
            self.preset = 1

    def refresh_display(self):
        buffer = " " + self._PATCH_MAP[self.preset] + " " + str(self.snap)
        self.display.show(buffer)

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

                for c_other in self.control_buttons:
                    if c_other.id != action_id:
                        c_other.set_passive()
                        self.np.set_pattern(pattern=c_other.pattern(), id=c_other.id)

            elif action == ControlAction.PRESET_UP:
                self.preset_update(1)
            elif action == ControlAction.PRESET_DOWN:
                self.preset_update(-1)

            if action != ControlAction.NONE:
                self.refresh_display()
                break

        self.np.poll()
