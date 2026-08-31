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
    snap_active=Wave((3, 0, 3), (30, 0, 30), period_ms=3000),
    snap_active_sec=Wave((0, 0, 6), (0, 0, 60), period_ms=3000),
    snap_passive=Solid((0, 0, 0)),
    snap_passive_sec=Solid((0, 0, 0)),
    looper_empty=Solid((0, 80, 0)),  # Green
    looper_stopped=Solid((0, 40, 40)),  # Yellow
    looper_playing=Solid((0, 40, 40)),  # Yellow
    looper_recording=Solid((80, 0, 0)),  # Red
    looper_overdubbing=Solid((80, 0, 0)),  # Red
)

CONTROLS_MAP = [
    [ControlAction.NONE, ControlAction.SNAP_1_2, ControlAction.NONE],
    [ControlAction.NONE, ControlAction.SNAP_3_4, ControlAction.PRESET_DOWN],
    [ControlAction.NONE, ControlAction.SNAP_5_6, ControlAction.PRESET_UP],
    [ControlAction.NONE, ControlAction.SNAP_7_8, ControlAction.NONE],
]

# LED mode for each NeoPixel group, in order
LED_MAP = [
    LEDMode.SNAP_1_2,
    LEDMode.SNAP_3_4,
    LEDMode.SNAP_5_6,
    LEDMode.SNAP_7_8,
]

# Send a mode message every time a snap message is sent
SEND_MODE_MSG = True

# Rotary encoder value targets
VALUE_PARAMS = [
    ValueParam(
        label="V", cc=7, min_value=0, max_value=127, initial=100, step=2
    ),  # Volume
    ValueParam(label="A", cc=12, min_value=0, max_value=127, initial=0),  # Param A
    ValueParam(label="B", cc=13, min_value=0, max_value=127, initial=0),  # Param B
]

# How long (ms) the value stays on screen after the last change
VALUE_HANG_MS = 1000

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
controls.append(ControlButton(pin=P_ROTARY_SW, action_long=ControlAction.VALUE_TOGGLE))
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

midi = MidiUsb(product_str=MIDI_PRODUCT_STR)

midi_controller = MidiController(
    control_buttons=controls,
    np=np_array,
    display=display,
    midi_map=MIDI_MAP,
    midi=midi,
    pattern_map=PATTERN_MAP,
    send_mode_msg=SEND_MODE_MSG,
    led_map=LED_MAP,
    control_encoder=control_encoder,
    value_params=VALUE_PARAMS,
    value_hang_ms=VALUE_HANG_MS,
)

while True:
    midi_controller.update()
    time.sleep_ms(UPDATE_INTERVAL)
