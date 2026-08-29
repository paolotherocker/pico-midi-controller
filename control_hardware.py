from utils.button import Button, ButtonEvent
from utils.ky040 import KY040, RotaryEvent


class ControlAction:
    """Action that can be executed by a Button Event"""

    NONE = 0
    SNAP_1_2 = 1
    SNAP_3_4 = 2
    SNAP_5_6 = 3
    SNAP_7_8 = 4
    PRESET_UP = 5
    PRESET_DOWN = 6
    LOOPER_REC_OD = 7
    LOOPER_STOP_PLAY = 8
    LOOPER_UNDO = 9
    LOOPER_CLEAR = 10
    VALUE_UP = 11
    VALUE_DOWN = 12
    VALUE_TOGGLE = 13


class LEDMode:
    """Display mode for a NeoPixel group."""

    NONE = 0
    SNAP_1_2 = 1
    SNAP_3_4 = 2
    SNAP_5_6 = 3
    SNAP_7_8 = 4
    LOOPER = 5


class Control:
    """Base class for control hardware."""

    def id(self) -> int:
        """Returns this control's identifier."""
        raise NotImplementedError

    def update(self) -> ControlAction:
        """Polls the hardware and returns the resulting action."""
        raise NotImplementedError


class ControlButton(Control):
    """Reports an action for a button press, short press, or long press."""

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
        """
        Args:
            id (int): Identifier for this button.
            pin (int): GPIO pin number.
            action_pressed (ControlAction, optional): Reported on press.
            action_short (ControlAction, optional): Reported on short press.
            action_long (ControlAction, optional): Reported on long press.
            debounce_ms (int, optional): Debounce time. Defaults to 10.
            long_press_ms (int, optional): Long press threshold. Defaults to 600.
        """
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
    """Reports an action for clockwise or counter-clockwise rotation."""

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
            id (int): Identifier for this encoder.
            dt_pin (int): Encoder DT pin.
            clk_pin (int): Encoder CLK pin.
            action_cw (ControlAction, optional): Reported on CW rotation.
                Defaults to ControlAction.VALUE_UP.
            action_ccw (ControlAction, optional): Reported on CCW rotation.
                Defaults to ControlAction.VALUE_DOWN.
            debounce_ms (int, optional): Debounce time. Defaults to 2.
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
