# Pico MIDI Controller

MicroPython firmware for a USB MIDI foot controller on a Raspberry Pi Pico (RP2040). Four foot switches, two menu buttons and a rotary encoder send MIDI Control Change (CC) messages, while NeoPixel groups and a four-digit display show the current state.

## Hardware

| Part | Quantity | Pins (GPIO) |
| --- | --- | --- |
| Momentary foot switches | 4 | 6, 7, 8, 9 |
| Menu buttons | 2 | 10 (preset up), 11 (preset down) |
| Rotary encoder with push switch (KY-040 type) | 1 | CLK 2, DT 3, SW 4 |
| TM1637 four-digit, seven-segment display | 1 | DIO 18, CLK 19 |
| WS2812B NeoPixels, 4 groups of 8 pixels on one data line | 32 pixels | 22 |

Pin numbers, group sizes and the USB product name are constants at the top of `main.py`.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Pin assignments, MIDI map, LED patterns, switch assignments and the main loop. This is the file you edit to configure the controller. |
| `midi_controller.py` | `MidiController`: polls the controls, dispatches actions, queues and sends MIDI, refreshes LEDs and display. |
| `control_hardware.py` | `ControlAction`, `LEDMode`, `ControlButton` and `ControlEncoder`. |
| `managers.py` | State for SNAP groups, presets, looper, stomps and value targets, plus `MidiMap`, `PatternMap`, `ValueParam` and `ConfigError`. |
| `hardware_test.py` | Standalone self-test for every input, the display, the NeoPixels and USB MIDI. |

## Dependencies

- [`micropython-utils`](https://github.com/paolotherocker/micropython-utils) provides `utils.button`, `utils.ky040`, `utils.midi` and `utils.neopixelmanager`.
- `usb-device-midi` from [`micropython-lib`](https://github.com/micropython/micropython-lib) provides the USB MIDI device class.
- [`micropython-tm1637`](https://github.com/mcauser/micropython-tm1637) drives the display.

The three libraries are also included as git submodules under `lib/` for reference. They are not deployed from there.

## Installation

Install the dependencies onto the Pico:

```bash
mpremote mip install usb-device-midi
mpremote mip install github:paolotherocker/micropython-utils
mpremote mip install github:mcauser/micropython-tm1637
```

Copy the firmware and reset the board:

```bash
mpremote fs cp main.py managers.py midi_controller.py control_hardware.py :
mpremote reset
```

If USB MIDI cannot be started (for example in a simulator), `main.py` prints each MIDI message to the serial console instead.

### Hardware self-test

Run `hardware_test.py` instead of `main.py` to check the wiring before using the full firmware:

```bash
mpremote run hardware_test.py
```

The Pico re-enumerates as a USB MIDI device during start-up, so `mpremote` will disconnect. Reconnect, or watch the display and a host MIDI monitor instead. Each foot switch sends CC 20 to 23, the menu buttons CC 30 and 31, the encoder switch CC 40 and the encoder rotation CC 50, all on channel 0.

## Programming the switches

Every button is a `ControlButton` with three independent action slots. Each slot takes a `ControlAction` and defaults to `ControlAction.NONE`.

| Slot | Fires | Typical use |
| --- | --- | --- |
| `action_pressed` | Immediately when the switch goes down (after debounce). | Fast actions where latency matters. |
| `action_short` | On release, if the switch was held for less than `long_press_ms`. | Normal tap. |
| `action_long` | Once, as soon as the switch has been held for `long_press_ms`, while it is still down. | Secondary or "careful" action. |

Timing is set per button with `debounce_ms` (default 10 ms) and `long_press_ms` (default 600 ms).

Slots are independent and can be combined, so note what a single gesture triggers:

- A short tap fires `action_pressed`, then `action_short` on release.
- A long hold fires `action_pressed`, then `action_long` at the threshold. `action_short` is not fired, and nothing further happens on release.
- If the same action is assigned to both `action_pressed` and `action_short`, a tap runs it twice. For a toggling action such as a stomp, that cancels itself out.

The underlying `Button` driver also reports a long release event, but `ControlButton` does not currently map it to an action.

Assignments are made when the buttons are created in `main.py`:

```python
ControlButton(
    pin=6,
    action_short=ControlAction.LOOPER_REC_OD,   # tap
    action_long=ControlAction.LOOPER_CLEAR,     # hold 600 ms
)
```

The encoder is a `ControlEncoder` with two slots, `action_cw` and `action_ccw`, defaulting to `VALUE_UP` and `VALUE_DOWN`.

## Assignable commands

All commands are `ControlAction` members. Message values come from the `MidiMap` in `main.py`; the numbers below are the shipped defaults, all on MIDI channel 0.

| Command | Effect | MIDI sent (default) | Display |
| --- | --- | --- | --- |
| `NONE` | Does nothing. | None. | None. |
| `SNAP_1_2` | Selects SNAP group 1/2. | CC 24, value 1 or 2. | ` S 1` or ` S 2` |
| `SNAP_3_4` | Selects SNAP group 3/4. | CC 24, value 3 or 4. | ` S 3` or ` S 4` |
| `SNAP_5_6` | Selects SNAP group 5/6. | CC 24, value 5 or 6. | ` S 5` or ` S 6` |
| `SNAP_7_8` | Selects SNAP group 7/8. | CC 24, value 7 or 8. | ` S 7` or ` S 8` |
| `PRESET_UP` | Next preset, wrapping from the last to 1. | CC 20, value 1, then CC 24, value 1. | ` P n` |
| `PRESET_DOWN` | Previous preset, wrapping from 1 to the last. | CC 20, value 2, then CC 24, value 1. | ` P n` |
| `LOOPER_REC_OD` | Record, then play, then overdub, toggling between play and overdub. | CC 25, value 1. | `rEC `, `PLAY` or `OdUb` |
| `LOOPER_STOP_PLAY` | Stops while recording, playing or overdubbing; plays when stopped. | CC 25, value 2. | `PLAY` or `StOP` |
| `LOOPER_CLEAR` | Clears the loop and returns to empty. | CC 25, value 3. | `CLr ` |
| `LOOPER_UNDO` | Sends undo; the transport state is unchanged. | CC 25, value 4. | `UndO` |
| `STOMP_1` to `STOMP_4` | Toggles the stomp on or off. | CC 26 to 29 for stomps 1 to 4, value 127 (on) or 0 (off). | `t1On`, `t1OF` and so on |
| `VALUE_UP` | Raises the selected value target by its step. | CC `cc` of the target, new value. | e.g. `V101` |
| `VALUE_DOWN` | Lowers the selected value target by its step. | CC `cc` of the target, new value. | e.g. `V099` |
| `VALUE_TOGGLE` | Selects the next value target, wrapping round. | CC of the new target, its current value. | e.g. `A  0` |
| `VALUE_DISP` | Shows the selected target and re-sends its current value. | CC of the target, current value. | e.g. `V100` |

### SNAP groups

The four SNAP groups map to eight snapshots. Pressing a group selects its first snapshot (1, 3, 5 or 7). Pressing the already-active group toggles to its second snapshot (2, 4, 6 or 8) and back. Each group remembers its own state while another group is active. With `send_mode_msg=True`, a mode message (CC 24, value `snap_mode_val`) is sent before every SNAP message.

### Presets

The controller counts presets from 1 to `preset_num` (default 8). Any preset command also resets SNAP to group 1/2, snapshot 1, and sends that SNAP value straight after the preset message, so a new preset never inherits the previous SNAP state. Presets are stepped, not selected directly, so the host is expected to follow the up and down messages. Stomp states are not changed by presets.

### Looper

The looper is a five-state machine: empty, recording, playing, overdubbing, stopped. The controller only tracks the state for the LEDs and display. The recording itself happens in the receiving device, which should respond to CC 25.

### Stomps

There are four independent stomps, each with its own `ControlAction` (`STOMP_1` to `STOMP_4`) and CC (`stomp_1_cc` to `stomp_4_cc` in the `MidiMap`). All stomps start off. Each press toggles that stomp and sends its CC with value 127 when on or 0 when off. The controller does not read the state back from the host, so it can drift if the host changes the stomp itself.

A stomp action needs its CC set in the `MidiMap`; otherwise start-up fails with `E005`. A NeoPixel group with a `STOMP_n` LED mode shows the `stomp_n` pattern while the stomp is on and is blank while it is off.

### Value targets

Value commands need at least one `ValueParam` in `value_params`; otherwise start-up fails with `E003`. Each target has a one-character display label, a CC number, a range, a step, a starting value and an optional channel override. Fast rotation accelerates the change: steps less than 40 ms apart use 4 times the step, and steps less than 80 ms apart use 2 times.

## Examples

Shipped layout, taps only (as in `main.py`). The four foot switches select SNAP groups on release, and the encoder switch shows the current value on press and cycles the target on a long press:

```python
ControlButton(pin=9, action_short=ControlAction.SNAP_1_2)
ControlButton(
    pin=P_ROTARY_SW,
    action_pressed=ControlAction.VALUE_DISP,
    action_long=ControlAction.VALUE_TOGGLE,
)
```

One switch as a looper control. Tap to record, play and overdub; hold to clear:

```python
ControlButton(
    pin=6,
    action_short=ControlAction.LOOPER_REC_OD,
    action_long=ControlAction.LOOPER_CLEAR,
)
```

A second looper switch. Tap to stop or play; hold to undo:

```python
ControlButton(
    pin=7,
    action_short=ControlAction.LOOPER_STOP_PLAY,
    action_long=ControlAction.LOOPER_UNDO,
)
```

Zero-latency SNAP selection. The action runs on press, and nothing is assigned to the other slots, so there is no double trigger:

```python
ControlButton(pin=8, action_pressed=ControlAction.SNAP_3_4)
```

A stomp on a foot switch, with its own NeoPixel group lit while it is on:

```python
ControlButton(pin=6, action_pressed=ControlAction.STOMP_1)

LED_MAP = [LEDMode.STOMP_1, LEDMode.SNAP_7_8, LEDMode.SNAP_3_4, LEDMode.SNAP_1_2]
```

Encoder stepping presets instead of values:

```python
ControlEncoder(
    dt_pin=P_ROTARY_DT,
    clk_pin=P_ROTARY_CLK,
    action_cw=ControlAction.PRESET_UP,
    action_ccw=ControlAction.PRESET_DOWN,
)
```

Two value targets on the encoder. Rotate to change the target, long-press the encoder switch to cycle between them:

```python
VALUE_PARAMS = [
    ValueParam(label="V", cc=7, min_value=0, max_value=127, initial=100),
    ValueParam(label="A", cc=12, min_value=0, max_value=127, initial=0, step=2),
]
```

## Configuration

- `MidiMap` sets the channel and the CC numbers and values for SNAP, preset and looper messages, plus the optional `stomp_1_cc` to `stomp_4_cc`. Values are clamped to 0 to 127 and the channel to 0 to 15. Unset stomp CCs are `None`.
- `PatternMap` sets a NeoPixel pattern for each of the eight active SNAP states, the shared passive SNAP state, the five looper states and the four stomp-on states (`stomp_1` to `stomp_4`). Unset patterns stay off. Patterns (`Solid`, `Off`, `Pulse`, `Flash`, `Wave`) come from `utils.neopixelmanager`.
- `LED_MAP` lists one `LEDMode` per NeoPixel group, in order: `SNAP_1_2`, `SNAP_3_4`, `SNAP_5_6`, `SNAP_7_8`, `LOOPER`, or `STOMP_1` to `STOMP_4`. A group is only repainted when its pattern changes, so animations are not restarted every frame.
- `display_hang_ms` sets how long each command message stays on the display. The display is blank otherwise.

Outgoing messages are queued (256 entries) and sent one every 8 ms.

## Error codes

If the configuration is invalid, all LEDs are turned off, the display shows the code and a `RuntimeError` is raised.

| Display | Meaning |
| --- | --- |
| `E001` | `led_map` has more entries than there are NeoPixel groups. |
| `E002` | A `ValueParam` has `min_value` greater than `max_value`. |
| `E003` | A value command is assigned but no `value_params` were given. |
| `E004` | The MIDI message queue overflowed. |
| `E005` | A stomp command is assigned but its CC is not set in the `MidiMap`. |
