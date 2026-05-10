"""
XPT2046 resistive touch controller driver for MicroPython / ESP32.

The XPT2046 shares the SPI bus with the ILI9341 display but uses a
separate CS line and requires a lower clock speed (~2 MHz).
Call get_touch() in a polling loop; it returns (x, y) screen
coordinates or None when no press is detected.
"""

import machine


# XPT2046 channel command bytes (12-bit, differential, power-down)
_CMD_X = const(0xD0)   # X position
_CMD_Y = const(0x90)   # Y position


class XPT2046:
    """
    Parameters
    ----------
    spi          : shared machine.SPI object
    cs           : touch chip-select Pin (output)
    width/height : screen dimensions in pixels
    x_min/x_max  : raw ADC range for X axis  (calibrate per board)
    y_min/y_max  : raw ADC range for Y axis  (calibrate per board)
    swap_xy      : swap X and Y axes (depends on display orientation)
    invert_x     : mirror the X axis
    invert_y     : mirror the Y axis
    """

    def __init__(self, spi, cs,
                 width=240, height=320,
                 x_min=200,  x_max=3800,
                 y_min=200,  y_max=3800,
                 swap_xy=False,
                 invert_x=False,
                 invert_y=False):
        self.spi      = spi
        self.cs       = cs
        self.width    = width
        self.height   = height
        self.x_min    = x_min
        self.x_max    = x_max
        self.y_min    = y_min
        self.y_max    = y_max
        self.swap_xy  = swap_xy
        self.invert_x = invert_x
        self.invert_y = invert_y

    # ── internal helpers ─────────────────────────────────────────

    def _read_adc(self, cmd):
        """Send one XPT2046 command and return the 12-bit ADC result."""
        # Lower the SPI speed for the touch controller
        self.spi.init(baudrate=2_000_000, polarity=0, phase=0)
        self.cs.off()
        self.spi.write(bytes([cmd]))
        data = self.spi.read(2)
        self.cs.on()
        # Restore display SPI speed
        self.spi.init(baudrate=40_000_000, polarity=0, phase=0)
        return ((data[0] << 8) | data[1]) >> 3

    def _sample(self, cmd, n=5):
        """Take *n* samples and return the median (noise rejection)."""
        vals = sorted(self._read_adc(cmd) for _ in range(n))
        return vals[n // 2]

    # ── public API ───────────────────────────────────────────────

    def get_touch(self):
        """
        Return (x, y) in screen pixels, or None if no touch detected.
        Values are clamped to [0, width-1] and [0, height-1].
        """
        raw_x = self._sample(_CMD_X)
        raw_y = self._sample(_CMD_Y)

        # Reject out-of-range values (panel not pressed)
        if raw_x < 100 or raw_x > 4000 or raw_y < 100 or raw_y > 4000:
            return None

        # Map to screen coordinates
        x = (raw_x - self.x_min) * self.width  // (self.x_max - self.x_min)
        y = (raw_y - self.y_min) * self.height // (self.y_max - self.y_min)

        if self.swap_xy:
            x, y = y, x
        if self.invert_x:
            x = self.width  - 1 - x
        if self.invert_y:
            y = self.height - 1 - y

        x = max(0, min(self.width  - 1, x))
        y = max(0, min(self.height - 1, y))
        return (x, y)

    def is_pressed(self):
        """Return True if the panel is currently being touched."""
        return self.get_touch() is not None
