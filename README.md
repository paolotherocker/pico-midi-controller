# Pico MIDI Controller

Firmware for a custom MIDI foot controller built on a Raspberry Pi Pico (RP2040) running MicroPython. The controller drives a bank of foot switches, each paired with its own NeoPixel (WS2812B) ring for visual feedback, alongside a display and a rotary encoder for navigation and patch selection.

## Hardware

- Raspberry Pi Pico or similar
- Multiple momentary foot switches, one per patch/preset slot
- One NeoPixel ring per foot switch, used for status/colour feedback
- A display (e.g. TM1639) for showing the current patch/bank
- A rotary encoder (with push button) for menu navigation and value changes

## Dependencies

- `usb-device-midi`, which is part of the built in [`micropython-lib`](https://github.com/micropython/micropython-lib)
- [`micropython-utils`](https://github.com/paolotherocker/micropython-utils), which provides the reusable `Button`, `NeopixelManager`, and `Rotary` classes used by `control_button.py` and `main.py`.
- [`micropython-tm1637`](https://github.com/mcauser/micropython-tm1637), which provides TM1637 tools for the display

Included here as a **git submodule*s* under `lib`, for code suggestions and version reference

### Deploying to Raspberry Pi Pico or similar

Install dependencies first
```bash
mpremote mip install usb-device-midi
mpremote mip install https://github.com/paolotherocker/micropython-utils.git
mpremote mip install https://github.com/mcauser/micropython-tm1637
```

Deploy code to USB target
```bash
mpremote fs cp *.py :
```
