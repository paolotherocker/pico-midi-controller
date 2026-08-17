from utils.button import Button, ButtonEvent
from utils.neopixelmanager import Pattern, Off, Pulse, Solid


class ControlAction:
    NONE = 0
    SNAP_1_2 = 1
    SNAP_3_4 = 2
    SNAP_5_6 = 3
    SNAP_7_8 = 4
    PRESET_UP = 5
    PRESET_DOWN = 6


class LEDMode:
    NONE = 0
    SNAP = 1


class ColorMap:

    def __init__(
        self,
        active_primary: tuple = (0, 0, 0),
        active_secondary: tuple = (0, 0, 0),
        passive_primary: tuple = (0, 0, 0),
        passive_secondary: tuple = (0, 0, 0),
    ):
        self.active_primary = active_primary
        self.active_secondary = active_secondary
        self.passive_primary = passive_primary
        self.passive_secondary = passive_secondary


class ControlButton(Button):
    def __init__(
        self,
        id: int,
        pin: int,
        action_short: ControlAction,
        action_long: ControlAction,
        led_mode: LEDMode,
        debounce_ms: int = 100,
        long_press_ms: int = 600,
        color_map: ColorMap = ColorMap(),
    ):
        super().__init__(pin, debounce_ms=debounce_ms, long_press_ms=long_press_ms)
        self.id = id
        self.action_short = action_short
        self.action_long = action_long
        self.led_mode = led_mode
        self.color_map = color_map

        self._active = False
        self._secondary = 0
        self._pattern = Off()
        self._snap_value = 0

    def set_passive(self):
        self._active = False

        if self.led_mode == LEDMode.SNAP:
            if self._secondary == 0:
                self._pattern = self.color_map.passive_primary
            else:
                self._pattern = self.color_map.passive_secondary

    def pattern(self) -> Pattern:
        if self.led_mode == LEDMode.NONE:
            return Off()
        else:
            return self._pattern

    def snap_value(self) -> int:
        return self._snap_value

    def exec_action(self, control_action: ControlAction):
        if control_action == ControlAction.NONE:
            return

        if control_action in (
            ControlAction.SNAP_1_2,
            ControlAction.SNAP_3_4,
            ControlAction.SNAP_5_6,
            ControlAction.SNAP_7_8,
        ):
            if self._active == True:
                self._secondary = 1 - self._secondary
            self._active = True

            if control_action == ControlAction.SNAP_1_2:
                self._snap_value = 1 + self._secondary
            if control_action == ControlAction.SNAP_3_4:
                self._snap_value = 3 + self._secondary
            if control_action == ControlAction.SNAP_5_6:
                self._snap_value = 5 + self._secondary
            if control_action == ControlAction.SNAP_7_8:
                self._snap_value = 7 + self._secondary

            if self.led_mode == LEDMode.SNAP:
                if self._secondary == 0:
                    self._pattern = self.color_map.active_primary
                else:
                    self._pattern = self.color_map.active_secondary

    def update(self) -> ControlAction:
        event = self.consume()
        action = ControlAction.NONE

        if event == ButtonEvent.SHORT_PRESS:
            action = self.action_short
        elif event == ButtonEvent.LONG_PRESS:
            action = self.action_long

        self.exec_action(action)

        return action
