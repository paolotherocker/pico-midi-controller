from utils.button import Button, ButtonEvent
from utils.ky040 import KY040, RotaryEvent


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
    VALUE_UP = 12
    VALUE_DOWN = 13
    VALUE_TOGGLE = 14


class LEDMode:
    """Behaviour descriptor of the LED string associated with a Control Button"""

    NONE = 0
    SNAP = 1
    LOOPER = 2


class Control:
    """Base class for all control hardware (buttons, encoders, etc.).

    Every subclass owns/builds its own hardware object(s) internally
    (composition, not inheritance) and must implement id() and update()
    so MidiController can poll any mix of hardware uniformly.
    """

    def id(self) -> int:
        """Identifier used by MidiController's managers (e.g. SnapManager)
        to tell hardware instances apart."""
        raise NotImplementedError

    def update(self) -> ControlAction:
        """Poll the underlying hardware and return the resulting
        ControlAction, or ControlAction.NONE if nothing happened."""
        raise NotImplementedError


class ControlButton(Control):
    """Thin event-to-action mapper.

    Wraps a debounced Button and knows which ControlAction to report for
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
        self._id = id
        self._button = Button(pin, debounce_ms=debounce_ms, long_press_ms=long_press_ms)
        self.action_pressed = action_pressed
        self.action_short = action_short
        self.action_long = action_long
        self.led_mode = led_mode

    def id(self) -> int:
        return self._id

    def update(self) -> ControlAction:
        event = self._button.consume()

        if event == ButtonEvent.PRESSED:
            return self.action_pressed
        elif event == ButtonEvent.SHORT_PRESS:
            return self.action_short
        elif event == ButtonEvent.LONG_PRESS:
            return self.action_long

        return ControlAction.NONE


class MenuButton(Control):
    """Thin event-to-action mapper, without LED-group tracking.

    Same as ControlButton but for buttons that don't drive a NeoPixel
    group (e.g. an encoder's built-in switch, standalone menu buttons).
    """

    def __init__(
        self,
        id: int,
        pin: int,
        action_pressed: ControlAction = ControlAction.NONE,
        action_short: ControlAction = ControlAction.NONE,
        action_long: ControlAction = ControlAction.NONE,
        debounce_ms: int = 10,
        long_press_ms: int = 600,
    ):
        self._id = id
        self._button = Button(pin, debounce_ms=debounce_ms, long_press_ms=long_press_ms)
        self.action_pressed = action_pressed
        self.action_short = action_short
        self.action_long = action_long

    def id(self) -> int:
        return self._id

    def update(self) -> ControlAction:
        event = self._button.consume()

        if event == ButtonEvent.PRESSED:
            return self.action_pressed
        elif event == ButtonEvent.SHORT_PRESS:
            return self.action_short
        elif event == ButtonEvent.LONG_PRESS:
            return self.action_long

        return ControlAction.NONE


class ControlEncoder(Control):
    """Rotary encoder event-to-action mapper (the encoder counterpart to
    ControlButton).

    Reports action_cw/action_ccw for CW/CCW rotation. Carries no switch
    or multi-value logic of its own -- pair it with a MenuButton (e.g. on
    the encoder's built-in switch pin) and a ValueManager to build a
    multi-target proportional control.
    """

    def __init__(
        self,
        id: int,
        dt_pin: int,
        clk_pin: int,
        action_cw: ControlAction = ControlAction.VALUE_UP,
        action_ccw: ControlAction = ControlAction.VALUE_DOWN,
        debounce_ms: int = 2,
    ):
        """
        Args:
            id (int): Identifier passed through to whatever manager handles
                the resulting ControlAction.
            dt_pin (int): Encoder DT pin.
            clk_pin (int): Encoder CLK pin.
            action_cw (ControlAction, optional): Reported on CW rotation.
                Defaults to ControlAction.VALUE_UP.
            action_ccw (ControlAction, optional): Reported on CCW rotation.
                Defaults to ControlAction.VALUE_DOWN.
            debounce_ms (int, optional): Rotary debounce. Defaults to 2.
        """
        self._id = id
        self._encoder = KY040(dt_pin=dt_pin, clk_pin=clk_pin, debounce_ms=debounce_ms)
        self.action_cw = action_cw
        self.action_ccw = action_ccw

    def id(self) -> int:
        return self._id

    def update(self) -> ControlAction:
        event = self._encoder.consume()

        if event == RotaryEvent.CW:
            return self.action_cw
        elif event == RotaryEvent.CCW:
            return self.action_ccw

        return ControlAction.NONE
