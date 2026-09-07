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
    VALUE_DISP = 14


class LEDMode:
    """Display mode for a NeoPixel group."""

    NONE = 0
    SNAP_1_2 = 1
    SNAP_3_4 = 2
    SNAP_5_6 = 3
    SNAP_7_8 = 4
    LOOPER = 5


class ActionMap:
    """Actions reported by a ControlButton for each button event."""

    PRESSED: ControlAction
    SHORT: ControlAction
    LONG: ControlAction

    def __init__(
        self,
        pressed: ControlAction = ControlAction.NONE,
        short: ControlAction = ControlAction.NONE,
        long: ControlAction = ControlAction.NONE,
    ):
        self.PRESSED = pressed
        self.SHORT = short
        self.LONG = long


class Control:
    """Base class for control hardware."""

    def update(self) -> ControlAction:
        """Polls the hardware and returns the resulting action."""
        raise NotImplementedError


class ControlButton(Control):
    """Reports an action for a button press, short press, or long press."""

    def __init__(
        self,
        pin: int,
        actions: ActionMap = ActionMap(),
        debounce_ms: int = 10,
        long_press_ms: int = 600,
    ):
        """
        Args:
            pin (int): GPIO pin number.
            actions (ActionMap, optional): Actions for the press/short/long events.
            debounce_ms (int, optional): Debounce time. Defaults to 10.
            long_press_ms (int, optional): Long press threshold. Defaults to 600.
        """
        self._button = Button(pin, debounce_ms=debounce_ms, long_press_ms=long_press_ms)
        self.actions = actions

    def update(self) -> ControlAction:
        event = self._button.consume()

        if event == ButtonEvent.PRESS:
            return self.actions.PRESSED
        elif event == ButtonEvent.SHORT_RELEASE:
            return self.actions.SHORT
        elif event == ButtonEvent.LONG_PRESS:
            return self.actions.LONG

        return ControlAction.NONE


class ControlEncoder(Control):
    """Reports an action for clockwise or counter-clockwise rotation."""

    def __init__(
        self,
        dt_pin: int,
        clk_pin: int,
        action_cw: ControlAction = ControlAction.VALUE_UP,
        action_ccw: ControlAction = ControlAction.VALUE_DOWN,
        debounce_ms: int = 2,
    ):
        """
        Args:
            dt_pin (int): Encoder DT pin.
            clk_pin (int): Encoder CLK pin.
            action_cw (ControlAction, optional): Reported on CW rotation.
                Defaults to ControlAction.VALUE_UP.
            action_ccw (ControlAction, optional): Reported on CCW rotation.
                Defaults to ControlAction.VALUE_DOWN.
            debounce_ms (int, optional): Debounce time. Defaults to 2.
        """
        self._encoder = KY040(dt_pin=dt_pin, clk_pin=clk_pin, debounce_ms=debounce_ms)
        self.action_cw = action_cw
        self.action_ccw = action_ccw

    def update(self) -> ControlAction:
        event = self._encoder.consume()

        if event == RotaryEvent.CW:
            return self.action_cw
        elif event == RotaryEvent.CCW:
            return self.action_ccw

        return ControlAction.NONE
