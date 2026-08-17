# Pico MIDI Controller

Firmware for a custom MIDI foot controller built on a Raspberry Pi Pico (RP2040) running MicroPython. The controller drives a bank of foot switches, each paired with its own NeoPixel (WS2812B) ring for visual feedback, alongside a display and a rotary encoder for navigation and patch selection.

## Hardware

- Raspberry Pi Pico (1)
- Multiple momentary foot switches, one per patch/preset slot
- One NeoPixel ring per foot switch, used for status/colour feedback
- A display (e.g. TM1639) for showing the current patch/bank
- A rotary encoder (with push button) for menu navigation and value changes

## Dependencies

This project depends on [`micropython-utils`](https://github.com/paolotherocker/micropython-utils), which provides the reusable `Button`, `NeopixelManager`, and `Rotary` classes used by `control_button.py` and `main.py`.

It is included as a **git submodule** under `lib/micropython-utils`, rather than installed via `mip`, so the exact commit is pinned and version-controlled alongside this repo.

### Deploying to the Pico

MicroPython needs the `utils` package reachable at import time.

```bash
mpremote mip install https://github.com/paolotherocker/micropython-utils.git
```

