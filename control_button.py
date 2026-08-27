from utils.button import Button, ButtonEvent


class ControlAction:
    NONE = 0
    HOLD = 1
    SNAP_1_2 = 2
    SNAP_3_4 = 3
    SNAP_5_6 = 4
    SNAP_7_8 = 5
    PRESET_UP = 6
    PRESET_DOWN = 7
    # Looper transport actions. All map onto the same MIDI CC
    # (looper_cc), distinguished only by CC value.
    REC_OD = 8
    STOP_PLAY = 9
    UNDO = 10
    CLEAR = 11


class LEDMode:
    """Tag telling MidiController how to compute a button's NeoPixel
    pattern. ControlButton itself holds no LED or application state --
    all of that lives in MidiController's Snap and Looper state machines,
    which is what actually drives the pixels for every button sharing a
    given mode."""

    NONE = 0
    SNAP = 1
    LOOPER = 2


class ControlButton(Button):
    """Thin event-to-action mapper.

    Just a debounced button that knows which ControlAction to report for
    a press/short-press/long-press, and which LEDMode group it belongs to.
    It does not track snap/looper/active/secondary state itself -- see
    MidiController for that.
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
