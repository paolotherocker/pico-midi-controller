from utils.button import Button, ButtonEvent
from utils.neopixelmanager import Pattern, Off


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


class PatternMap:

    def __init__(
        self,
        active_primary: Pattern = Off(),
        active_secondary: Pattern = Off(),
        passive_primary: Pattern = Off(),
        passive_secondary: Pattern = Off(),
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
                    self._pattern = self.pattern_map.active_primary
                else:
                    self._pattern = self.pattern_map.passive_primary
            # Secondary
            else:
                if self._active == True:
                    self._pattern = self.pattern_map.active_secondary
                else:
                    self._pattern = self.pattern_map.passive_secondary

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
        self._update_pattern()

        return action
