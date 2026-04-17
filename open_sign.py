"""
ESP32 Open Sign Controller (MicroPython)
=========================================
Turns a relay ON every day at 11:00 AM and OFF at 8:00 PM local time.

Hardware
--------
* ESP32 DA WROOM module
* Relay module connected to RELAY_PIN (default GPIO 26)
  - IN  → GPIO 26
  - VCC → 3.3 V or 5 V (check your relay module spec)
  - GND → GND

Configuration
-------------
Edit the constants in the "User configuration" section below:
  WIFI_SSID     – your WiFi network name
  WIFI_PASSWORD – your WiFi password
  UTC_OFFSET    – hours offset from UTC for your local timezone
                  e.g. -5 for US Eastern Standard, +1 for Central European
  OPEN_HOUR     – hour (0-23) to turn the relay ON  (default 11 → 11 AM)
  CLOSE_HOUR    – hour (0-23) to turn the relay OFF (default 20 → 8 PM)
  RELAY_PIN     – GPIO pin number connected to the relay IN
  RELAY_ON      – logic level that activates the relay
                  True  = active-high relay (most common blue relay boards)
                  False = active-low relay  (some optocoupler relay boards)

Deployment
----------
1. Flash MicroPython firmware to the ESP32.
2. Edit the user configuration constants below.
3. Upload this file to the ESP32 as ``main.py`` (so it runs on boot)
   using a tool such as Thonny, rshell, or ampy:
       ampy --port /dev/ttyUSB0 put open_sign.py /main.py
4. Power-cycle the ESP32 — it will connect to WiFi, sync the clock,
   then automatically manage the relay every day.
"""

import machine
import network
import ntptime
import time
import utime

# ---------------------------------------------------------------------------
# User configuration — edit these values
# ---------------------------------------------------------------------------
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Hours offset from UTC for your local timezone (fractional hours are supported,
# e.g. UTC-5:30 → -5.5).  Does NOT automatically handle DST.
UTC_OFFSET = -5  # e.g. -5 for US Eastern Standard Time

OPEN_HOUR = 11   # 11 AM — relay turns ON
CLOSE_HOUR = 20  # 8 PM  — relay turns OFF

RELAY_PIN = 26   # GPIO pin connected to relay IN
RELAY_ON = True  # True = active-high, False = active-low

# How often (in seconds) to re-sync the NTP clock (default: every hour)
NTP_SYNC_INTERVAL = 3600

# How often (in seconds) to check whether to open/close (default: 30 s)
CHECK_INTERVAL = 30
# ---------------------------------------------------------------------------

# Derived relay signal levels
_RELAY_ACTIVE = RELAY_ON
_RELAY_INACTIVE = not RELAY_ON


def connect_wifi(ssid, password, max_wait=20):
    """Connect to the given WiFi network.  Raises RuntimeError on failure."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    print(f"Connecting to WiFi '{ssid}' …")
    wlan.connect(ssid, password)
    for _ in range(max_wait):
        if wlan.isconnected():
            break
        time.sleep(1)
    if not wlan.isconnected():
        raise RuntimeError(
            f"Could not connect to WiFi '{ssid}'. "
            "Check WIFI_SSID and WIFI_PASSWORD."
        )
    print("WiFi connected —", wlan.ifconfig())
    return wlan


def sync_ntp(retries=5, delay=5):
    """Synchronise the RTC from NTP.  Retries on failure."""
    for attempt in range(1, retries + 1):
        try:
            ntptime.settime()
            print("NTP sync successful —", utime.localtime())
            return
        except Exception as exc:
            print(f"NTP sync attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(delay)
    print("WARNING: NTP sync failed after all retries. Time may be inaccurate.")


def local_hour():
    """Return the current local hour (0-23) applying UTC_OFFSET."""
    # utime.time() returns seconds since 2000-01-01 00:00:00 UTC on MicroPython
    utc_seconds = utime.time()
    offset_seconds = int(UTC_OFFSET * 3600)
    local_t = utime.localtime(utc_seconds + offset_seconds)
    # local_t: (year, month, mday, hour, minute, second, weekday, yearday)
    return local_t[3]


def set_relay(pin, active):
    """Drive relay pin to active or inactive state."""
    pin.value(1 if active else 0)


def main():
    # Initialise relay pin — start with relay OFF
    relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
    set_relay(relay, _RELAY_INACTIVE)
    print(f"Relay initialised on GPIO {RELAY_PIN} (inactive).")

    # Connect to WiFi (required for NTP)
    connect_wifi(WIFI_SSID, WIFI_PASSWORD)

    # Initial NTP sync
    sync_ntp()

    last_ntp_sync = utime.time()

    print(
        f"Open Sign scheduler running — "
        f"ON at {OPEN_HOUR:02d}:00, OFF at {CLOSE_HOUR:02d}:00 "
        f"(UTC{UTC_OFFSET:+g})"
    )

    while True:
        now = utime.time()

        # Re-sync NTP periodically
        if now - last_ntp_sync >= NTP_SYNC_INTERVAL:
            sync_ntp()
            last_ntp_sync = utime.time()

        hour = local_hour()
        sign_should_be_on = OPEN_HOUR <= hour < CLOSE_HOUR

        if sign_should_be_on:
            set_relay(relay, _RELAY_ACTIVE)
            print(f"[hour={hour:02d}] Sign ON  — relay active")
        else:
            set_relay(relay, _RELAY_INACTIVE)
            print(f"[hour={hour:02d}] Sign OFF — relay inactive")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
