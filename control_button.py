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
        active_0: Pattern = Off(),
        active_1: Pattern = Off(),
        passive_0: Pattern = Off(),
        passive_1: Pattern = Off(),
        hold: Pattern = Off(),
    ):
        self.active_0 = active_0
        self.active_1 = active_1
        self.passive_0 = passive_0
        self.passive_1 = passive_1
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

        self.pattern_snap = (
            (pattern_map.passive_0, pattern_map.passive_1),
            (pattern_map.active_0, pattern_map.active_1),
        )
        self.pattern_hold = pattern_map.hold

        self._active = False
        self._secondary = False
        self._pattern = Off()
        self._snap_value = 0

    def _update_pattern(self):
        if self.led_mode == LEDMode.SNAP:
            self._pattern = self.pattern_snap[self._active][self._secondary]

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
            self._pattern = self.pattern_hold
            return

        elif control_action in (
            ControlAction.SNAP_1_2,
            ControlAction.SNAP_3_4,
            ControlAction.SNAP_5_6,
            ControlAction.SNAP_7_8,
        ):
            if self._active == True:
                self._secondary = not self._secondary
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
