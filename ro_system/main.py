"""
RO Water System Controller
==========================
ESP32-WROOM-32  +  HiLetgo ILI9341 2.8" TFT (XPT2046 touch)

Features
--------
* Beach-themed background with animated ocean waves
* Restaurant name displayed prominently
* 3 configurable RO timer stages (touch-activated pump relay)
* Progress bar showing time remaining
* Buzzer alert when the water container is full
* Rotating safety slides when idle (hand-washing, sharps, clean area)

Upload all three files to the ESP32 root with Thonny:
    ili9341.py   xpt2046.py   main.py
"""

import machine
import time
from ili9341 import ILI9341, color565
from xpt2046 import XPT2046

# ─────────────────────────────────────────────────────────────────
#  USER CONFIGURATION  ← edit these to match your setup
# ─────────────────────────────────────────────────────────────────

RESTAURANT_NAME = "OCEAN BISTRO"       # displayed on every screen

# Three RO timer stages: (button label, duration in seconds)
TIMER_STAGES = [
    ("STAGE 1",  5 * 60),             #  5 minutes
    ("STAGE 2", 10 * 60),             # 10 minutes
    ("STAGE 3", 15 * 60),             # 15 minutes
]

IDLE_TIMEOUT_S  = 30                  # seconds before safety slides appear
SLIDE_DURATION_S = 10                 # seconds each safety slide is shown

# ─────────────────────────────────────────────────────────────────
#  HARDWARE PINS
# ─────────────────────────────────────────────────────────────────

# ILI9341 display — VSPI bus
PIN_SCK  = 18
PIN_MOSI = 23
PIN_MISO = 19
PIN_CS   = 22   # display chip-select
PIN_DC   = 21   # data / command
PIN_RST  = 17   # reset
PIN_BL   = 16   # backlight (or wire directly to 3.3 V)

# XPT2046 touch — shares the same SPI bus, separate CS
PIN_T_CS = 4

# Outputs
PIN_PUMP   = 25  # relay: HIGH = pump ON
PIN_BUZZER = 26  # piezo buzzer (PWM)

# ─────────────────────────────────────────────────────────────────
#  COLOUR PALETTE  (RGB-565)
# ─────────────────────────────────────────────────────────────────

C_BLACK    = color565(  0,   0,   0)
C_WHITE    = color565(255, 255, 255)
C_NAVY     = color565( 10,  20,  70)
C_SKY_LT   = color565(185, 225, 255)
C_SKY_MID  = color565(110, 185, 245)
C_SKY_DK   = color565( 55, 130, 220)
C_SUN      = color565(255, 215,   0)
C_SUN_GLOW = color565(255, 170,  50)
C_SAND     = color565(235, 208, 155)
C_SAND_DK  = color565(200, 170, 110)
C_GREEN    = color565( 30, 200,  80)
C_GREEN_DK = color565(  0, 130,  40)
C_RED      = color565(220,  40,  40)
C_RED_DK   = color565(150,   0,   0)
C_ORANGE   = color565(255, 140,   0)
C_YELLOW   = color565(255, 215,   0)
C_GRAY     = color565(110, 115, 125)
C_GRAY_LT  = color565(180, 185, 200)
C_BTN_BLUE = color565( 30, 100, 200)
C_BTN_HLT  = color565( 70, 160, 255)
C_PURPLE   = color565(120,  40, 180)

# Wave colour gradient (16 shades, cycles to animate the ocean)
_WAVE = [
    color565(  0,  45, 120),
    color565(  0,  65, 148),
    color565(  0,  88, 168),
    color565(  0, 110, 188),
    color565( 10, 130, 202),
    color565( 22, 150, 212),
    color565( 45, 165, 218),
    color565( 80, 182, 228),
    color565(125, 202, 238),
    color565(170, 220, 246),
    color565(210, 236, 252),
    color565(170, 220, 246),
    color565(125, 202, 238),
    color565( 80, 182, 228),
    color565( 45, 165, 218),
    color565( 22, 150, 212),
]
_WAVE_N = len(_WAVE)

# Safety slide themes: (title, accent colour, content lines)
SAFETY_SLIDES = [
    (
        "WASH YOUR HANDS",
        C_BTN_BLUE,
        [
            "Before handling food",
            "After restroom use",
            "After touching face",
            "After handling trash",
            "Scrub for 20 seconds",
        ],
    ),
    (
        "SHARPS SAFETY",
        C_RED_DK,
        [
            "Never reach into bins",
            "Use cut-proof gloves",
            "Keep blades covered",
            "Report all injuries",
            "Dispose in sharps bin",
        ],
    ),
    (
        "KEEP AREA CLEAN",
        C_GREEN_DK,
        [
            "Wipe surfaces hourly",
            "Clean spills at once",
            "Empty bins when full",
            "Sanitize equipment",
            "Follow FIFO storage",
        ],
    ),
]

# ─────────────────────────────────────────────────────────────────
#  SCREEN LAYOUT CONSTANTS  (240 × 320 portrait)
# ─────────────────────────────────────────────────────────────────

W = 240
H = 320

SKY_Y   =   0;  SKY_H   =  50   # sky gradient
OCEAN_Y =  50;  OCEAN_H =  75   # animated ocean bands
SAND_Y  = 125;  SAND_H  =  13   # sand strip
NAME_Y  = 142                   # restaurant name row (2× scale = 16 px)
DIV_Y   = 162;  DIV_H   =   3   # divider line
BTN1_Y  = 168                   # Stage 1 button top
BTN2_Y  = 228                   # Stage 2 button top
BTN3_Y  = 268                   # Stage 3 button top
BTN_H   =  54                   # button height
BTN_X   =   8                   # button left margin
BTN_W   = 224                   # button width

# Timer screen
TIM_OCEAN_Y = 30;  TIM_OCEAN_H = 55
TIM_LABEL_Y = 90                # "STAGE X" label
TIM_TIME_Y  = 112               # large countdown digits (3× = 24 px)
TIM_BAR_Y   = 175               # progress bar
TIM_PUMP_Y  = 210               # PUMP: ACTIVE row
TIM_STOP_Y  = 250               # STOP button

# ─────────────────────────────────────────────────────────────────
#  HARDWARE SETUP
# ─────────────────────────────────────────────────────────────────

# Backlight always on
bl = machine.Pin(PIN_BL, machine.Pin.OUT, value=1)

# SPI bus shared by display and touch
spi = machine.SPI(
    2,
    baudrate=40_000_000,
    polarity=0,
    phase=0,
    sck=machine.Pin(PIN_SCK),
    mosi=machine.Pin(PIN_MOSI),
    miso=machine.Pin(PIN_MISO),
)

# Display
tft = ILI9341(
    spi,
    cs=machine.Pin(PIN_CS,  machine.Pin.OUT, value=1),
    dc=machine.Pin(PIN_DC,  machine.Pin.OUT),
    rst=machine.Pin(PIN_RST, machine.Pin.OUT, value=1),
)

# Touch
touch = XPT2046(
    spi,
    cs=machine.Pin(PIN_T_CS, machine.Pin.OUT, value=1),
    # ── Touch calibration ──────────────────────────────────────────
    # If taps register in the wrong position, adjust these values.
    # Run the calibration helper (see README) to find your board's values.
    x_min=200,  x_max=3800,
    y_min=200,  y_max=3800,
    swap_xy=False,
    invert_x=True,    # MADCTL=0x48 mirrors X; invert touch to match
    invert_y=False,
)

# Pump relay
pump = machine.Pin(PIN_PUMP, machine.Pin.OUT, value=0)

# Buzzer PWM (duty=0 = silent)
buzzer = machine.PWM(machine.Pin(PIN_BUZZER), freq=2000, duty=0)

# ─────────────────────────────────────────────────────────────────
#  STATE MACHINE
# ─────────────────────────────────────────────────────────────────

STATE_HOME  = 0   # main menu with beach background
STATE_TIMER = 1   # countdown running
STATE_DONE  = 2   # timer complete — buzzer + notification
STATE_SLIDE = 3   # safety slide rotation (idle screensaver)

state          = STATE_HOME
stage_idx      = 0           # which timer stage (0, 1, 2)
timer_end_ms   = 0           # absolute ticks_ms when timer expires
timer_total_s  = 0           # duration of current stage in seconds
last_touch_ms  = time.ticks_ms()
slide_idx      = 0
slide_start_ms = time.ticks_ms()
wave_phase     = 0
last_wave_ms   = time.ticks_ms()
done_start_ms  = 0

# ─────────────────────────────────────────────────────────────────
#  DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────

def draw_sky():
    """Draw a 3-band sky gradient."""
    band = SKY_H // 3
    tft.fill_rect(0, SKY_Y,          W, band,          C_SKY_LT)
    tft.fill_rect(0, SKY_Y + band,   W, band,          C_SKY_MID)
    tft.fill_rect(0, SKY_Y + band*2, W, SKY_H - band*2, C_SKY_DK)
    # Sun (upper-right)
    tft.fill_circle(200, 22, 18, C_SUN_GLOW)
    tft.fill_circle(200, 22, 14, C_SUN)


def draw_ocean(y_start, height, phase):
    """Draw animated ocean as shifting colour bands."""
    bands  = height // 5          # ~5 bands per call
    band_h = height // bands
    for i in range(bands):
        c = _WAVE[(i + phase) % _WAVE_N]
        tft.fill_rect(0, y_start + i * band_h, W, band_h, c)
    # Fill any leftover pixels with the last colour
    drawn = bands * band_h
    if drawn < height:
        tft.fill_rect(0, y_start + drawn, W, height - drawn, _WAVE[(bands - 1 + phase) % _WAVE_N])


def draw_sand():
    tft.fill_rect(0, SAND_Y,          W, SAND_H // 2,          C_SAND)
    tft.fill_rect(0, SAND_Y + SAND_H // 2, W, SAND_H - SAND_H // 2, C_SAND_DK)


def draw_button(x, y, w, h, label, accent=C_BTN_BLUE, text_scale=2):
    """Draw a rounded-style button (rectangle with accent border)."""
    # Shadow / dark outline
    tft.fill_rect(x + 2, y + 2, w, h, C_BLACK)
    # Fill
    tft.fill_rect(x, y, w, h, accent)
    # Lighter top edge for depth
    tft.hline(x, y, w, C_BTN_HLT)
    tft.hline(x, y + 1, w, C_BTN_HLT)
    # Label centred
    tft.draw_text_centered(
        x + w // 2, y + (h - 8 * text_scale) // 2,
        label, C_WHITE, accent, text_scale
    )


def draw_progress_bar(x, y, w, h, pct, fg=C_GREEN, bg=C_GRAY):
    """Draw a filled progress bar. pct = 0.0 … 1.0"""
    tft.fill_rect(x, y, w, h, bg)
    filled = int(w * max(0.0, min(1.0, pct)))
    if filled > 0:
        tft.fill_rect(x, y, filled, h, fg)
    tft.rect(x, y, w, h, C_WHITE)


def fmt_time(seconds):
    """Format seconds as MM:SS string."""
    m = seconds // 60
    s = seconds % 60
    return "{:02d}:{:02d}".format(m, s)


# ─────────────────────────────────────────────────────────────────
#  FULL SCREEN RENDERS
# ─────────────────────────────────────────────────────────────────

def render_home():
    """Draw the complete home / main-menu screen."""
    tft.fill(C_NAVY)
    draw_sky()
    draw_ocean(OCEAN_Y, OCEAN_H, wave_phase)
    draw_sand()

    # Restaurant name
    name_x = (W - len(RESTAURANT_NAME) * 8 * 2) // 2
    tft.fill_rect(0, NAME_Y, W, 18, C_NAVY)
    tft.draw_text(name_x, NAME_Y, RESTAURANT_NAME, C_YELLOW, C_NAVY, 2)

    # Divider
    tft.fill_rect(0, DIV_Y, W, DIV_H, C_BTN_HLT)

    # Three timer buttons
    labels = [s[0] for s in TIMER_STAGES]
    draw_button(BTN_X, BTN1_Y, BTN_W, BTN_H - 4, labels[0], C_BTN_BLUE, 2)
    draw_button(BTN_X, BTN2_Y, BTN_W, BTN_H - 4, labels[1], C_PURPLE,   2)
    draw_button(BTN_X, BTN3_Y, BTN_W, BTN_H - 4, labels[2], C_GREEN_DK, 2)

    # Sub-labels showing durations
    for i, (label, secs) in enumerate(TIMER_STAGES):
        btn_y = [BTN1_Y, BTN2_Y, BTN3_Y][i]
        dur   = "{:d} min".format(secs // 60)
        dur_x = (W - len(dur) * 8) // 2
        tft.draw_text(dur_x, btn_y + BTN_H - 16, dur, C_GRAY_LT,
                      [C_BTN_BLUE, C_PURPLE, C_GREEN_DK][i], 1)


def render_timer(remaining_s, total_s, stage_label):
    """Draw the timer-running screen."""
    tft.fill(C_NAVY)

    # Compact sky + name header
    tft.fill_rect(0, 0, W, 28, C_SKY_DK)
    hdr_x = (W - len(RESTAURANT_NAME) * 8) // 2
    tft.draw_text(hdr_x, 8, RESTAURANT_NAME, C_YELLOW, C_SKY_DK, 1)

    # Mini ocean
    draw_ocean(TIM_OCEAN_Y, TIM_OCEAN_H, wave_phase)

    # Stage label
    tft.fill_rect(0, TIM_LABEL_Y, W, 20, C_NAVY)
    tft.draw_text_centered(W // 2, TIM_LABEL_Y + 2, stage_label + "  RUNNING",
                           C_GRAY_LT, C_NAVY, 1)

    # Large countdown
    tft.fill_rect(0, TIM_TIME_Y, W, 28, C_NAVY)
    ts = fmt_time(remaining_s)
    tft.draw_text_centered(W // 2, TIM_TIME_Y, ts, C_WHITE, C_NAVY, 3)

    # Progress bar
    pct = 1.0 - (remaining_s / total_s) if total_s > 0 else 1.0
    tft.fill_rect(0, TIM_BAR_Y, W, 30, C_NAVY)
    draw_progress_bar(10, TIM_BAR_Y + 4, W - 20, 20, pct)
    pct_str = "{:d}%".format(int(pct * 100))
    tft.draw_text_centered(W // 2, TIM_BAR_Y + 7, pct_str, C_WHITE, C_NAVY, 1)

    # Pump status
    tft.fill_rect(0, TIM_PUMP_Y, W, 18, C_NAVY)
    tft.draw_text_centered(W // 2, TIM_PUMP_Y, "PUMP: ACTIVE", C_GREEN, C_NAVY, 1)

    # Stop button
    draw_button(20, TIM_STOP_Y, W - 40, 54, "STOP", C_RED, 2)


def render_done():
    """Draw the 'container full' alert screen."""
    tft.fill(C_NAVY)
    tft.fill_rect(0, 0, W, 50, C_GREEN_DK)
    tft.draw_text_centered(W // 2, 14, "CONTAINER FULL!", C_WHITE, C_GREEN_DK, 2)

    tft.fill_rect(10, 60, W - 20, 3, C_GREEN)

    tft.draw_text_centered(W // 2, 80,  "Water is ready.",    C_GRAY_LT, C_NAVY, 1)
    tft.draw_text_centered(W // 2, 100, "Please remove the",  C_GRAY_LT, C_NAVY, 1)
    tft.draw_text_centered(W // 2, 116, "container now.",     C_GRAY_LT, C_NAVY, 1)

    # Pulsing ring (drawn once; buzzer pulses separately)
    tft.fill_circle(W // 2, 190, 42, C_GREEN_DK)
    tft.fill_circle(W // 2, 190, 36, C_GREEN)
    tft.fill_circle(W // 2, 190, 26, C_NAVY)
    tft.draw_text_centered(W // 2, 184, "OK", C_WHITE, C_NAVY, 2)

    tft.draw_text_centered(W // 2, 250, "Touch screen to", C_GRAY_LT, C_NAVY, 1)
    tft.draw_text_centered(W // 2, 264, "return to menu.", C_GRAY_LT, C_NAVY, 1)

    draw_button(20, 285, W - 40, 28, "DISMISS", C_BTN_BLUE, 1)


def render_slide(idx):
    """Draw one safety slide (full screen)."""
    title, accent, lines = SAFETY_SLIDES[idx]
    tft.fill(C_NAVY)

    # Header bar
    tft.fill_rect(0, 0, W, 52, accent)
    tft.fill_circle(W // 2, -10, 70, C_BLACK)     # decorative arc
    tft.fill_rect(0, 0, W, 50, accent)            # re-cover arc
    tft.draw_text_centered(W // 2, 16, title, C_WHITE, accent, 2)

    # Slide counter dots
    for i in range(len(SAFETY_SLIDES)):
        cx = W // 2 + (i - len(SAFETY_SLIDES) // 2) * 18
        tft.fill_circle(cx, 46, 4, C_WHITE if i == idx else C_GRAY)

    # Content lines
    for i, line in enumerate(lines):
        ly = 68 + i * 30
        # Bullet
        tft.fill_circle(20, ly + 6, 4, accent)
        tft.draw_text(30, ly, line, C_WHITE, C_NAVY, 1)

    # "Touch to dismiss" footer
    tft.fill_rect(0, H - 28, W, 28, accent)
    tft.draw_text_centered(W // 2, H - 20, "Touch anywhere to return", C_WHITE, accent, 1)

    # Slide number
    sl_str = "{}/{}".format(idx + 1, len(SAFETY_SLIDES))
    tft.draw_text(W - len(sl_str) * 8 - 6, H - 20, sl_str, C_WHITE, accent, 1)


# ─────────────────────────────────────────────────────────────────
#  BUZZER HELPERS  (non-blocking pattern via ticks_ms)
# ─────────────────────────────────────────────────────────────────

def update_buzzer(now_ms, active):
    """
    Call every loop iteration.  When *active* is True the buzzer plays
    three short beeps (300 ms each) then pauses for ~1.4 s (2 s total).
    """
    if not active:
        buzzer.duty(0)
        return
    t = time.ticks_ms() % 2000
    if t < 300 or 450 < t < 750 or 900 < t < 1200:
        buzzer.duty(512)
    else:
        buzzer.duty(0)


# ─────────────────────────────────────────────────────────────────
#  TOUCH HIT-TEST HELPERS
# ─────────────────────────────────────────────────────────────────

def in_rect(pos, x, y, w, h):
    """Return True if touch position *pos* falls inside the rectangle."""
    if pos is None:
        return False
    px, py = pos
    return x <= px <= x + w and y <= py <= y + h


# ─────────────────────────────────────────────────────────────────
#  INITIAL RENDER
# ─────────────────────────────────────────────────────────────────

render_home()

# ─────────────────────────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────────────────────────

WAVE_INTERVAL_MS   =  80   # update wave animation ~12 fps
TIMER_REFRESH_MS   = 500   # refresh countdown display twice per second
last_timer_draw_ms = 0
last_remaining_s   = -1

while True:
    now_ms = time.ticks_ms()

    # ── Touch polling ────────────────────────────────────────────
    pos = touch.get_touch()
    if pos:
        last_touch_ms = now_ms

        if state == STATE_HOME:
            if in_rect(pos, BTN_X, BTN1_Y, BTN_W, BTN_H):
                stage_idx     = 0
            elif in_rect(pos, BTN_X, BTN2_Y, BTN_W, BTN_H):
                stage_idx     = 1
            elif in_rect(pos, BTN_X, BTN3_Y, BTN_W, BTN_H):
                stage_idx     = 2
            else:
                stage_idx     = -1

            if stage_idx >= 0:
                _, secs       = TIMER_STAGES[stage_idx]
                timer_total_s = secs
                timer_end_ms  = time.ticks_add(now_ms, secs * 1000)
                pump.on()
                state         = STATE_TIMER
                last_remaining_s = -1  # force immediate redraw
                render_timer(secs, timer_total_s, TIMER_STAGES[stage_idx][0])

        elif state == STATE_TIMER:
            if in_rect(pos, 20, TIM_STOP_Y, W - 40, 54):
                pump.off()
                state = STATE_HOME
                render_home()

        elif state == STATE_DONE:
            pump.off()
            buzzer.duty(0)
            state = STATE_HOME
            render_home()

        elif state == STATE_SLIDE:
            buzzer.duty(0)
            state = STATE_HOME
            last_touch_ms = now_ms
            render_home()

    # ── Wave animation ───────────────────────────────────────────
    if time.ticks_diff(now_ms, last_wave_ms) >= WAVE_INTERVAL_MS:
        last_wave_ms = now_ms
        wave_phase   = (wave_phase + 1) % _WAVE_N

        if state == STATE_HOME:
            draw_ocean(OCEAN_Y, OCEAN_H, wave_phase)
        elif state == STATE_TIMER:
            draw_ocean(TIM_OCEAN_Y, TIM_OCEAN_H, wave_phase)

    # ── Timer countdown ──────────────────────────────────────────
    if state == STATE_TIMER:
        remaining_ms = time.ticks_diff(timer_end_ms, now_ms)
        remaining_s  = max(0, remaining_ms // 1000)

        if remaining_s == 0:
            # Timer complete
            pump.off()
            done_start_ms = now_ms
            state = STATE_DONE
            render_done()

        elif (remaining_s != last_remaining_s and
              time.ticks_diff(now_ms, last_timer_draw_ms) >= TIMER_REFRESH_MS):
            last_timer_draw_ms = now_ms
            last_remaining_s   = remaining_s
            # Refresh just the dynamic parts (time + bar)
            tft.fill_rect(0, TIM_TIME_Y, W, 28, C_NAVY)
            tft.draw_text_centered(W // 2, TIM_TIME_Y,
                                   fmt_time(remaining_s), C_WHITE, C_NAVY, 3)
            pct = 1.0 - (remaining_s / timer_total_s)
            draw_progress_bar(10, TIM_BAR_Y + 4, W - 20, 20, pct)
            pct_str = "{:d}%".format(int(pct * 100))
            tft.draw_text_centered(W // 2, TIM_BAR_Y + 7, pct_str, C_WHITE, C_NAVY, 1)

    # ── Buzzer (DONE state) ──────────────────────────────────────
    update_buzzer(now_ms, state == STATE_DONE)

    # ── Idle → safety slides ─────────────────────────────────────
    if state == STATE_HOME:
        idle_s = time.ticks_diff(now_ms, last_touch_ms) // 1000
        if idle_s >= IDLE_TIMEOUT_S:
            state          = STATE_SLIDE
            slide_idx      = 0
            slide_start_ms = now_ms
            render_slide(slide_idx)

    elif state == STATE_SLIDE:
        elapsed_s = time.ticks_diff(now_ms, slide_start_ms) // 1000
        if elapsed_s >= SLIDE_DURATION_S:
            slide_idx      = (slide_idx + 1) % len(SAFETY_SLIDES)
            slide_start_ms = now_ms
            render_slide(slide_idx)

    time.sleep_ms(20)
