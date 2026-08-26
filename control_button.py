from utils.button import Button, ButtonEvent
from utils.neopixelmanager import Pattern, Off


class ControlAction:
    NONE = 0
    HOLD = 1
    SNAP_1_2 = 2
    SNAP_3_4 = 3
    SNAP_5_6 = 4
    SNAP_7_8 = 5
    PRESET_UP = 6
    PRESET_DOWN = 7


class LEDMode:
    NONE = 0
    SNAP = 1


class PatternMap:

    def __init__(
        self,
        snap_active_0: Pattern = Off(),
        snap_active_1: Pattern = Off(),
        snap_passive_0: Pattern = Off(),
        snap_passive_1: Pattern = Off(),
        hold: Pattern = Off(),
    ):
        self.snap_active_0 = snap_active_0
        self.snap_active_1 = snap_active_1
        self.snap_passive_0 = snap_passive_0
        self.snap_passive_1 = snap_passive_1
        self.hold = hold


class ControlButton(Button):
    def __init__(
        self,
        id: int,
        pin: int,
        action_pressed: ControlAction = ControlAction.NONE,
        action_short: ControlAction = ControlAction.NONE,
        action_long: ControlAction = ControlAction.NONE,
        led_mode: LEDMode = LEDMode.NONE,
        debounce_ms: int = 10,
        long_press_ms: int = 600,
        pattern_map: PatternMap = PatternMap(),
    ):
        super().__init__(pin, debounce_ms=debounce_ms, long_press_ms=long_press_ms)
        self.id = id
        self.action_pressed = action_pressed
        self.action_short = action_short
        self.action_long = action_long
        self.led_mode = led_mode
        self.pattern_map = pattern_map

        self._active = False
        self._secondary = 0
        self._pattern = Off()
        self._snap_value = 0

    def _update_pattern(self):
        if self.led_mode == LEDMode.SNAP:
            # Primary
            if self._secondary == 0:
                if self._active == True:
                    self._pattern = self.pattern_map.snap_active_0
                else:
                    self._pattern = self.pattern_map.snap_passive_0
            # Secondary
            else:
                if self._active == True:
                    self._pattern = self.pattern_map.snap_active_1
                else:
                    self._pattern = self.pattern_map.snap_passive_1

    def set_passive(self):
        self._active = False
        self._update_pattern()

    def consume_pattern(self) -> Pattern | None:
        """Returns a new pattern if availble, otherwise returns None"""
        pattern = self._pattern
        self._pattern = None
        return pattern

    def snap_value(self) -> int:
        return self._snap_value

    def exec_action(self, control_action: ControlAction):
        if control_action == ControlAction.NONE:
            return

        elif control_action == ControlAction.HOLD:
            self._pattern = self.pattern_map.hold
            return

        elif control_action in (
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

        self._update_pattern()

    def update(self) -> ControlAction:
        event = self.consume()
        action = ControlAction.NONE

        if event == ButtonEvent.PRESSED:
            action = self.action_pressed
        elif event == ButtonEvent.SHORT_PRESS:
            action = self.action_short
        elif event == ButtonEvent.LONG_PRESS:
            action = self.action_long

        self.exec_action(action)

        return action
