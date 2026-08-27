from utils.button import Button, ButtonEvent


class ControlAction:
    """Action that can be executed by a Button Event"""

    NONE = 0
    HOLD = 1
    SNAP_1_2 = 2
    SNAP_3_4 = 3
    SNAP_5_6 = 4
    SNAP_7_8 = 5
    PRESET_UP = 6
    PRESET_DOWN = 7
    LOOPER_REC_OD = 8
    LOOPER_STOP_PLAY = 9
    LOOPER_UNDO = 10
    LOOPER_CLEAR = 11


class LEDMode:
    """Behaviour descriptor of the LED string associated with a Control Button"""

    NONE = 0
    SNAP = 1
    LOOPER = 2


class ControlButton(Button):
    """Thin event-to-action mapper.

    Just a debounced button that knows which ControlAction to report for
    a press/short-press/long-press, and which LEDMode group it belongs to.
    """

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
    ):
        super().__init__(pin, debounce_ms=debounce_ms, long_press_ms=long_press_ms)
        self.id = id
        self.action_pressed = action_pressed
        self.action_short = action_short
        self.action_long = action_long
        self.led_mode = led_mode

    def update(self) -> ControlAction:
        event = self.consume()

        if event == ButtonEvent.PRESSED:
            return self.action_pressed
        elif event == ButtonEvent.SHORT_PRESS:
            return self.action_short
        elif event == ButtonEvent.LONG_PRESS:
            return self.action_long

        return ControlAction.NONE
