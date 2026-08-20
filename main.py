"""
Install dependencies:
mpremote mip install usb-device-midi neopixel
mpremote mip install github:mcauser/micropython-tm1637
mpremote fs cp -r lib_common :/lib
"""

from machine import Pin
from utils.rotary import Rotary
from utils.neopixelmanager import NeoPixelManager, Pulse, Solid, Off
import time
from tm1637 import TM1637
from midi_controller import MidiController, MidiMap
from control_button import ControlButton, ControlAction, LEDMode, PatternMap

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
P_ROTARY_CLK = 14
P_ROTARY_DT = 15
P_ROTARY_SW = 13
# Extra button pins
P_MENU_BUTTONS = [10, 11]

MIDI_MAP = MidiMap(
    channel=0, snap_cc=24, preset_cc=20, preset_up_val=1, preset_down_val=2
)

CONTROLS_MAP = [
    [ControlAction.SNAP_1_2, ControlAction.NONE, LEDMode.SNAP],
    [ControlAction.SNAP_3_4, ControlAction.PRESET_DOWN, LEDMode.SNAP],
    [ControlAction.SNAP_5_6, ControlAction.PRESET_UP, LEDMode.SNAP],
    [ControlAction.SNAP_7_8, ControlAction.NONE, LEDMode.SNAP],
]


SNAP_PATTERN_MAP = PatternMap(
    Pulse(color1=(0, 80, 0), color2=(0, 60, 20), period_ms=5000),
    Pulse(color1=(0, 0, 80), color2=(0, 20, 60), period_ms=5000),
    Solid(color=(0, 10, 0)),
    Solid(color=(0, 0, 10)),
)

controls = []
for i in range(4):
    controls.append(
        ControlButton(
            id=i,
            pin=P_CONTROLS[i],
            action_short=CONTROLS_MAP[i][0],
            action_long=CONTROLS_MAP[i][1],
            led_mode=CONTROLS_MAP[i][2],
            pattern_map=SNAP_PATTERN_MAP,
        )
    )


encoder = Rotary(dt_pin=P_ROTARY_DT, clk_pin=P_ROTARY_CLK)
tm = TM1637(clk=Pin(P_DISP_CLK), dio=Pin(P_DISP_DIO))

np_array = NeoPixelManager(pin_id=P_NP, n=NP_STRIP_LEN * NP_STRIP_NUM)
for i in range(NP_STRIP_NUM):
    np_array.add_subset(NP_STRIP_LEN)

midi_controller = MidiController(
    control_buttons=controls,
    np=np_array,
    encoder=encoder,
    display=tm,
    midi_map=MIDI_MAP,
)

while True:
    midi_controller.update()
    time.sleep_ms(UPDATE_INTERVAL)
