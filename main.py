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
from patch_manager import PatchManager
from control_button import ControlButton, ControlAction, LEDMode, PatternMap

# Display
p_disp_dio = 2
p_disp_clk = 3
# Neopixel
p_np = 15  # Data pin
k_np_strip_len = 8  # Number of leds per strip
k_np_strip_num = 4  # Number of strips
# Control pins
p_controls = [10, 11, 12, 13]
# Encoder pins
p_rotary_clk = 16
p_rotary_dt = 17
p_rotary_sw = 18
# Extra button pins
p_menu_buttons = [19, 20]

controls_mapping = [
    [ControlAction.SNAP_1_2, ControlAction.NONE, LEDMode.SNAP],
    [ControlAction.SNAP_3_4, ControlAction.NONE, LEDMode.SNAP],
    [ControlAction.SNAP_5_6, ControlAction.PRESET_UP, LEDMode.SNAP],
    [ControlAction.SNAP_7_8, ControlAction.PRESET_DOWN, LEDMode.SNAP],
]

snap_pattern_map = PatternMap(
    Pulse(color1=(0, 200, 32), color2=(0, 200, 96), period_ms=5000),
    Pulse(color1=(0, 32, 200), color2=(0, 96, 200), period_ms=5000),
    Solid(color=(0, 50, 8)),
    Solid(color=(0, 8, 50)),
)

controls = []
for i in range(4):
    controls.append(
        ControlButton(
            id=i,
            pin=p_controls[i],
            action_short=controls_mapping[i][0],
            action_long=controls_mapping[i][1],
            led_mode=controls_mapping[i][2],
            pattern_map=snap_pattern_map,
        )
    )


encoder = Rotary(dt_pin=p_rotary_dt, clk_pin=p_rotary_clk)
tm = TM1637(clk=Pin(p_disp_clk), dio=Pin(p_disp_dio))

np_array = NeoPixelManager(pin_id=p_np, n=k_np_strip_len * k_np_strip_num)
for i in range(k_np_strip_num):
    np_array.add_subset(k_np_strip_len)

patch_manager = PatchManager(
    control_buttons=controls, np=np_array, encoder=encoder, display=tm
)

while True:
    patch_manager.update()
    time.sleep_ms(5)
