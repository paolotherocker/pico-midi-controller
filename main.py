"""
Install dependencies:
mpremote mip install usb-device-midi neopixel
mpremote mip install github:mcauser/micropython-tm1637
mpremote fs cp -r lib_common :/lib
"""

from machine import Pin
from utils.neopixelmanager import NeoPixelManager, Pulse, Solid, Off, Wave
import time
from tm1637 import TM1637
from utils.midi import MidiUsb
from midi_controller import MidiController, MidiMap, PatternMap, ValueParam
from control_hardware import ControlButton, ControlEncoder, ControlAction, LEDMode

# Main refresh interval
UPDATE_INTERVAL = 5

# Display
P_DISP_DIO = 18
P_DISP_CLK = 19
# Neopixel
P_NP = 22  # Data pin
NP_STRIP_LEN = 8  # Number of leds per strip
NP_STRIP_NUM = 4  # Number of strips
# Control pins
P_CONTROLS = [6, 7, 8, 9]
# Encoder pins
P_ROTARY_CLK = 2
P_ROTARY_DT = 3
P_ROTARY_SW = 4
# Extra button pins
P_MENU_BUTTONS = [10, 11]

# USB MIDI device name shown on the host
MIDI_PRODUCT_STR = "Pico Midi Controller"

MIDI_MAP = MidiMap(
    channel=0,
    snap_cc=24,
    snap_mode_val=0,
    preset_cc=20,
    preset_up_val=1,
    preset_down_val=2,
    preset_mode_val=0,
    looper_cc=25,
    looper_ro_val=1,
    looper_sp_val=2,
    looper_clear_val=3,
    looper_undo_val=4,
)

PATTERN_MAP = PatternMap(
    snap_active_1=Wave((0, 0, 6), (0, 0, 60), period_ms=4000, spread=1),  # Blue
    snap_active_2=Wave((2, 0, 4), (20, 0, 40), period_ms=2000, spread=1),  # Purple
    snap_active_3=Wave((6, 0, 0), (60, 0, 0), period_ms=4000, spread=1),  # Red
    snap_active_4=Wave((5, 0, 1), (50, 0, 10), period_ms=2000, spread=1),  # Pink
    snap_active_5=Wave((0, 0, 6), (0, 0, 60), period_ms=4000, spread=1),  # Blue
    snap_active_6=Wave((2, 0, 4), (20, 0, 40), period_ms=2000, spread=1),  # Purple
    snap_active_7=Wave((6, 0, 0), (60, 0, 0), period_ms=4000, spread=1),  # Red
    snap_active_8=Wave((5, 0, 1), (50, 0, 10), period_ms=2000, spread=1),  # Pink
    snap_passive=Off(),
    looper_empty=Off(),
    looper_stopped=Solid((0, 40, 0)),  # Green
    looper_playing=Wave((3, 3, 0), (30, 30, 0), period_ms=2000, spread=1),  # Yellow
    looper_recording=Wave((6, 0, 0), (60, 0, 0), period_ms=2000, spread=1),  # Red
    looper_overdubbing=Wave((6, 0, 0), (60, 0, 0), period_ms=2000, spread=1),  # Red
)

CONTROLS_MAP = [
    [ControlAction.NONE, ControlAction.SNAP_5_6, ControlAction.NONE],
    [ControlAction.NONE, ControlAction.SNAP_7_8, ControlAction.NONE],
    [ControlAction.NONE, ControlAction.SNAP_3_4, ControlAction.NONE],
    [ControlAction.NONE, ControlAction.SNAP_1_2, ControlAction.NONE],
]

# LED mode for each NeoPixel group, in order
LED_MAP = [
    LEDMode.SNAP_5_6,
    LEDMode.SNAP_7_8,
    LEDMode.SNAP_3_4,
    LEDMode.SNAP_1_2,
]

# Send a mode message every time a snap message is sent
SEND_MODE_MSG = True

# Rotary encoder value targets
VALUE_PARAMS = [
    ValueParam(
        label="V", cc=7, min_value=0, max_value=127, initial=100, step=1
    ),  # Volume
    # ValueParam(label="A", cc=12, min_value=0, max_value=127, initial=0),  # Param A
    # ValueParam(label="B", cc=13, min_value=0, max_value=127, initial=0),  # Param B
]

# How long (ms) a command message stays on the display
DISPLAY_HANG_MS = 500

controls = []
for i in range(4):
    controls.append(
        ControlButton(
            pin=P_CONTROLS[i],
            action_pressed=CONTROLS_MAP[i][0],
            action_short=CONTROLS_MAP[i][1],
            action_long=CONTROLS_MAP[i][2],
        )
    )

# Encoder switch and extra menu buttons
controls.append(
    ControlButton(
        pin=P_ROTARY_SW,
        action_pressed=ControlAction.VALUE_DISP,
        action_long=ControlAction.VALUE_TOGGLE,
    )
)
controls.append(
    ControlButton(pin=P_MENU_BUTTONS[0], action_pressed=ControlAction.PRESET_UP)
)
controls.append(
    ControlButton(pin=P_MENU_BUTTONS[1], action_pressed=ControlAction.PRESET_DOWN)
)

# Rotary encoder
control_encoder = ControlEncoder(dt_pin=P_ROTARY_DT, clk_pin=P_ROTARY_CLK)

display = TM1637(clk=Pin(P_DISP_CLK), dio=Pin(P_DISP_DIO))

np_array = NeoPixelManager(pin_id=P_NP, n=NP_STRIP_LEN * NP_STRIP_NUM)
for i in range(NP_STRIP_NUM):
    np_array.add_subset(NP_STRIP_LEN)

# Without USB MIDI support (e.g. in a simulator), MIDI messages are printed
midi_usb = None
try:
    midi_usb = MidiUsb(product_str=MIDI_PRODUCT_STR)
except (RuntimeError, OSError) as err:
    print("USB MIDI unavailable ({}); printing MIDI messages instead".format(err))

midi_controller = MidiController(
    control_buttons=controls,
    np=np_array,
    display=display,
    midi_map=MIDI_MAP,
    midi_usb=midi_usb,
    pattern_map=PATTERN_MAP,
    send_mode_msg=SEND_MODE_MSG,
    led_map=LED_MAP,
    control_encoder=control_encoder,
    value_params=VALUE_PARAMS,
    display_hang_ms=DISPLAY_HANG_MS,
)

while True:
    midi_controller.update()
    time.sleep_ms(UPDATE_INTERVAL)
