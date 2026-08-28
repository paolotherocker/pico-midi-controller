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
from midi_controller import MidiController, MidiMap, PatternMap
from control_button import ControlButton, ControlAction, LEDMode

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
    channel=0,
    snap_cc=24,
    preset_cc=20,
    preset_up_val=1,
    preset_down_val=2,
    looper_cc=25,
    looper_ro_val=1,
    looper_sp_val=2,
    looper_clear_val=3,
    looper_undo_val=4,
)

PATTERN_MAP = PatternMap(
    snap_active=Pulse((0, 200, 0), (0, 180, 20), period_ms=5000),
    snap_active_sec=Pulse((0, 0, 200), (0, 20, 180), period_ms=5000),
    snap_passive=Solid((0, 80, 0)),
    snap_passive_sec=Solid((0, 0, 80)),
    looper_empty=Solid((0, 100, 0)),  # Green
    looper_stopped=Solid((100, 100, 0)),  # Yellow
    looper_playing=Solid((200, 200, 0)),  # Yellow
    looper_recording=Solid((200, 0, 0)),  # Red
    looper_overdubbing=Solid((200, 0, 0)),  # Red
)

CONTROLS_MAP = [
    [ControlAction.NONE, ControlAction.SNAP_1_2, ControlAction.NONE],
    [ControlAction.NONE, ControlAction.SNAP_3_4, ControlAction.PRESET_DOWN],
    [ControlAction.NONE, ControlAction.SNAP_5_6, ControlAction.PRESET_UP],
    [ControlAction.NONE, ControlAction.SNAP_7_8, ControlAction.NONE],
]

LED_MAP = [LEDMode.SNAP, LEDMode.SNAP, LEDMode.SNAP, LEDMode.SNAP]


controls = []
for i in range(4):
    controls.append(
        ControlButton(
            id=i,
            pin=P_CONTROLS[i],
            action_pressed=CONTROLS_MAP[i][0],
            action_short=CONTROLS_MAP[i][1],
            action_long=CONTROLS_MAP[i][2],
            led_mode=LED_MAP[i],
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
    pattern_map=PATTERN_MAP,
)

while True:
    midi_controller.update()
    time.sleep_ms(UPDATE_INTERVAL)
