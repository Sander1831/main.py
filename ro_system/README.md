# RO Water System Controller — Setup Guide

## Hardware

| Component | Details |
|-----------|---------|
| Microcontroller | ESP32-WROOM-32 (ESP32 DevKit V1) |
| Display | HiLetgo ILI9341 2.8" SPI TFT 240×320 with XPT2046 touch |
| Pump | 5 V / 12 V relay module |
| Buzzer | Passive piezo buzzer |
| Power | 5 V via USB or external supply |

---

## Wiring Diagram

```
ESP32-WROOM-32                  ILI9341 Display Board
──────────────                  ─────────────────────
3.3V  ──────────────────────►  VCC
GND   ──────────────────────►  GND
GPIO18 (SCK)  ──────────────►  CLK  (T_CLK shares this line)
GPIO23 (MOSI) ──────────────►  MOSI (T_DIN shares this line)
GPIO19 (MISO) ──────────────►  MISO (T_DO  shares this line)
GPIO22        ──────────────►  CS   (display chip-select)
GPIO21        ──────────────►  DC   (data/command)
GPIO17        ──────────────►  RST  (reset)
GPIO16        ──────────────►  LED  (backlight — or wire to 3.3V)
GPIO4         ──────────────►  T_CS (touch chip-select)

ESP32-WROOM-32                  Relay Module (Pump)
──────────────                  ───────────────────
GPIO25        ──────────────►  IN   (signal)
5V            ──────────────►  VCC
GND           ──────────────►  GND
                               COM  ──► pump supply +
                               NO   ──► pump +
                               (pump − to supply −)

ESP32-WROOM-32                  Passive Buzzer
──────────────                  ─────────────
GPIO26        ──────────────►  + (longer leg)
GND           ──────────────►  − (shorter leg)
```

> **Note:** The ILI9341 board is 3.3 V / 5 V compatible and has
> on-board level-shifting, so connecting directly to the ESP32's
> 3.3 V GPIO pins is safe.

---

## Files to upload with Thonny

Upload all three files to the **root** of the ESP32 (not inside a folder):

```
ili9341.py      ← display driver
xpt2046.py      ← touch driver
main.py         ← your application (this is the file in ro_system/)
```

### Step-by-step in Thonny

1. Install **MicroPython** on your ESP32 via  
   *Tools → Options → Interpreter → Install or update MicroPython*.  
   Choose **ESP32** and the correct COM port.

2. Open each `.py` file from this folder in Thonny.

3. Go to **File → Save copy…** → **MicroPython device** and save with
   the same filename (e.g. `ili9341.py`).  
   Repeat for all three files.

4. Power-cycle the ESP32 — `main.py` runs automatically on boot.

---

## Customising the application

Open `main.py` and edit the **USER CONFIGURATION** section near the top:

```python
RESTAURANT_NAME = "OCEAN BISTRO"   # ← change to your name

TIMER_STAGES = [
    ("STAGE 1",  5 * 60),          # ← change durations (in seconds)
    ("STAGE 2", 10 * 60),
    ("STAGE 3", 15 * 60),
]

IDLE_TIMEOUT_S  = 30               # seconds before safety slides appear
SLIDE_DURATION_S = 10              # seconds each slide is displayed
```

---

## Touch calibration

If taps register in the wrong screen position, adjust the constants
in `main.py` where the `XPT2046` object is created:

```python
touch = XPT2046(
    spi, cs=...,
    x_min=200,  x_max=3800,   # ← raw ADC range for your board
    y_min=200,  y_max=3800,
    swap_xy=False,             # set True if X/Y axes are swapped
    invert_x=True,             # set False if left/right is wrong
    invert_y=False,            # set True  if top/bottom is wrong
)
```

To find the raw values for your specific board, add this temporary
snippet to `main.py` and read the REPL output while touching corners:

```python
# Calibration helper — remove when done
while True:
    pos = touch.get_touch()
    if pos:
        print(pos)
    time.sleep_ms(200)
```

---

## Screen overview

| State | Shown when |
|-------|-----------|
| **Home** | Startup / after dismissing any screen |
| **Timer running** | After tapping a stage button; shows countdown + progress bar |
| **Container full** | Timer reaches zero; buzzer activates |
| **Safety slides** | No touch for 30 seconds (hand-washing, sharps, clean area) |

---

## Changing GPIO pins

If you need different pin numbers, update the `PIN_*` constants in
`main.py`:

```python
PIN_SCK  = 18   # SPI clock
PIN_MOSI = 23   # SPI data out
PIN_MISO = 19   # SPI data in
PIN_CS   = 22   # display CS
PIN_DC   = 21   # display D/C
PIN_RST  = 17   # display reset
PIN_BL   = 16   # backlight
PIN_T_CS = 4    # touch CS
PIN_PUMP   = 25 # relay signal
PIN_BUZZER = 26 # buzzer
```

Avoid GPIO 0, 2, 5, and 12 — these are boot-sensitive on ESP32-WROOM-32.
