"""
Bare-minimum hardware self-test for the MIDI foot controller.

Run this standalone on the Pico (instead of main.py) to confirm every
piece of control hardware, the display, the NeoPixel rings, and USB
MIDI output all work, before loading the full MidiController
application. Uses the same drivers as main.py: utils.button,
utils.ky040, tm1637, utils.neopixelmanager, and utils.midi (which
itself needs `mpremote mip install usb-device-midi`, same as main.py).

Behaviour:
- Start-up: each NeoPixel group lights in turn, display shows "Init"
  then "Rdy ". The Pico re-enumerates as a USB MIDI device at this
  point; if you're connected via mpremote you'll need to reconnect.
- Press a foot switch (pins 6, 7, 8, 9) -> its NeoPixel group flashes,
  display shows "SW1".."SW4", and a CC message is sent on channel 0,
  controllers 20-23, value 127.
- Press a menu button (pins 10, 11) -> display shows "MN1"/"MN2" and
  sends CC 30/31, value 127.
- Press the encoder's push switch (pin 4) -> display shows "ENC " and
  sends CC 40, value 127.
- Rotate the encoder CW/CCW -> a counter on the display counts up/down,
  the direction prints to the console, and CC 50 is sent with the
  counter's value (clamped to 0-127).

Open a MIDI monitor on the host (e.g. a DAW's MIDI input list, or a
tool like MIDI Monitor / MIDI-OX) to confirm the messages arrive.
"""

from machine import Pin
import time
from tm1637 import TM1637
from utils.button import Button, ButtonEvent
from utils.ky040 import KY040, RotaryEvent
from utils.neopixelmanager import NeoPixelManager, Solid, Off
from utils.midi import MidiUsb, ControlChange

# --- Pins (must match main.py) ---
P_DISP_DIO = 18
P_DISP_CLK = 19
P_NP = 22
NP_STRIP_LEN = 8
NP_STRIP_NUM = 4
P_CONTROLS = [6, 7, 8, 9]
P_ROTARY_CLK = 2
P_ROTARY_DT = 3
P_ROTARY_SW = 4
P_MENU_BUTTONS = [10, 11]

UPDATE_INTERVAL_MS = 5
FLASH_MS = 300
DISPLAY_HOLD_MS = 500

COLOUR = (0, 120, 0)  # green

# --- MIDI CC test map ---
MIDI_CHANNEL = 0
SW_CC = [20, 21, 22, 23]
MENU_CC = [30, 31]
ENC_SW_CC = 40
ENC_ROTATE_CC = 50

# --- Hardware setup ---
display = TM1637(clk=Pin(P_DISP_CLK), dio=Pin(P_DISP_DIO))
display.brightness(3)

np_array = NeoPixelManager(pin_id=P_NP, n=NP_STRIP_LEN * NP_STRIP_NUM)
for _ in range(NP_STRIP_NUM):
    np_array.add_subset(NP_STRIP_LEN)
strip_ids = list(range(NP_STRIP_NUM))

foot_buttons = [Button(pin) for pin in P_CONTROLS]
menu_buttons = [Button(pin) for pin in P_MENU_BUTTONS]
encoder_button = Button(P_ROTARY_SW)
encoder = KY040(dt_pin=P_ROTARY_DT, clk_pin=P_ROTARY_CLK)

midi = MidiUsb(product_str="MIDI Controller Hardware Test")


def send_cc(controller, value):
    """Sends a MIDI CC via the shared midi library if the USB MIDI
    interface is open, and prints it either way so the test still
    reports something over the REPL."""
    value = max(0, min(127, value))
    print("CC ch={} cc={} val={}".format(MIDI_CHANNEL, controller, value))
    if midi.is_open():
        midi.send_message(ControlChange(MIDI_CHANNEL, controller, value))


# --- Start-up self-test: sweep each NeoPixel group in turn ---
display.show("Init")
for sid in strip_ids:
    np_array.set_pattern(pattern=Solid(COLOUR), id=sid)
    np_array.poll()
    np_array.write()
    time.sleep_ms(150)
    np_array.set_pattern(pattern=Off(), id=sid)
    np_array.poll()
    np_array.write()
display.show("Rdy ")
print("Self-test sweep complete. Waiting for input...")

encoder_count = 0
display_until = 0
flash_until = [0] * NP_STRIP_NUM


def show(text, hold_ms=DISPLAY_HOLD_MS):
    global display_until
    display.show(text)
    print(text)
    display_until = time.ticks_add(time.ticks_ms(), hold_ms)


def flash(strip_id, hold_ms=FLASH_MS):
    np_array.set_pattern(pattern=Solid(COLOUR), id=strip_id)
    flash_until[strip_id] = time.ticks_add(time.ticks_ms(), hold_ms)


while True:
    for i, btn in enumerate(foot_buttons):
        event = btn.consume()
        if event == ButtonEvent.PRESSED:
            flash(strip_ids[i])
            show("SW{}".format(i + 1))
            send_cc(SW_CC[i], 127)

    for i, btn in enumerate(menu_buttons):
        event = btn.consume()
        if event == ButtonEvent.PRESSED:
            show("MN{}".format(i + 1))
            send_cc(MENU_CC[i], 127)

    if encoder_button.consume() == ButtonEvent.PRESSED:
        show("ENC ")
        send_cc(ENC_SW_CC, 127)

    rotation = encoder.consume()
    if rotation == RotaryEvent.CW:
        encoder_count = min(127, encoder_count + 1)
        show("C{:03d}".format(encoder_count))
        send_cc(ENC_ROTATE_CC, encoder_count)
    elif rotation == RotaryEvent.CCW:
        encoder_count = max(0, encoder_count - 1)
        show("A{:03d}".format(encoder_count))
        send_cc(ENC_ROTATE_CC, encoder_count)

    now = time.ticks_ms()
    for sid in strip_ids:
        if flash_until[sid] and time.ticks_diff(now, flash_until[sid]) > 0:
            np_array.set_pattern(pattern=Off(), id=sid)
            flash_until[sid] = 0

    if display_until and time.ticks_diff(now, display_until) > 0:
        display.show("Rdy ")
        display_until = 0

    np_array.poll()
    time.sleep_ms(UPDATE_INTERVAL_MS)
