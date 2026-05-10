"""
ILI9341 2.8" SPI TFT display driver for MicroPython / ESP32.
Supports fill_rect, hline, vline, fill_circle, rect, and scaled text
rendered via MicroPython's built-in 8x8 framebuf font.
"""

import time
import framebuf
from micropython import const

# ILI9341 command bytes
_SWRESET = const(0x01)
_SLPOUT  = const(0x11)
_NORON   = const(0x13)
_INVOFF  = const(0x20)
_DISPON  = const(0x29)
_CASET   = const(0x2A)
_PASET   = const(0x2B)
_RAMWR   = const(0x2C)
_MADCTL  = const(0x36)
_COLMOD  = const(0x3A)
_FRMCTR1 = const(0xB1)
_DFUNCTR = const(0xB6)
_PWCTR1  = const(0xC0)
_PWCTR2  = const(0xC1)
_VMCTR1  = const(0xC5)
_VMCTR2  = const(0xC7)
_GMCTRP1 = const(0xE0)
_GMCTRN1 = const(0xE1)


def color565(r, g, b):
    """Pack (r, g, b) 0-255 values into a 16-bit RGB-565 word."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


class ILI9341:
    """
    Minimal ILI9341 driver.

    Parameters
    ----------
    spi  : machine.SPI object (40 MHz recommended)
    cs   : chip-select Pin (output)
    dc   : data/command Pin (output)
    rst  : reset Pin (output)
    w, h : logical width and height in pixels (default 240 × 320)
    """

    def __init__(self, spi, cs, dc, rst, w=240, h=320):
        self.spi = spi
        self.cs  = cs
        self.dc  = dc
        self.rst = rst
        self.w   = w
        self.h   = h
        self._init_display()

    # ── low-level helpers ──────────────────────────────────────────

    def _cmd(self, cmd):
        self.dc.off()
        self.cs.off()
        self.spi.write(bytes([cmd]))
        self.cs.on()

    def _dat(self, data):
        self.dc.on()
        self.cs.off()
        self.spi.write(data if isinstance(data, (bytes, bytearray)) else bytes([data]))
        self.cs.on()

    def _set_window(self, x0, y0, x1, y1):
        self._cmd(_CASET)
        self._dat(bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._cmd(_PASET)
        self._dat(bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._cmd(_RAMWR)

    # ── initialisation ────────────────────────────────────────────

    def _init_display(self):
        self.rst.off()
        time.sleep_ms(50)
        self.rst.on()
        time.sleep_ms(150)

        self._cmd(_SWRESET); time.sleep_ms(150)
        self._cmd(_SLPOUT);  time.sleep_ms(150)

        self._cmd(_FRMCTR1); self._dat(bytes([0x00, 0x18]))
        self._cmd(_DFUNCTR); self._dat(bytes([0x08, 0x82, 0x27]))
        self._cmd(_PWCTR1);  self._dat(0x23)
        self._cmd(_PWCTR2);  self._dat(0x10)
        self._cmd(_VMCTR1);  self._dat(bytes([0x3E, 0x28]))
        self._cmd(_VMCTR2);  self._dat(0x86)
        self._cmd(_MADCTL);  self._dat(0x48)   # MX | BGR — portrait
        self._cmd(_COLMOD);  self._dat(0x55)   # 16-bit colour
        self._cmd(_INVOFF)
        self._cmd(_NORON);   time.sleep_ms(10)

        self._cmd(_GMCTRP1)
        self._dat(bytes([0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08,
                         0x4E, 0xF1, 0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00]))
        self._cmd(_GMCTRN1)
        self._dat(bytes([0x00, 0x0E, 0x14, 0x03, 0x11, 0x07,
                         0x31, 0xC1, 0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F]))

        self._cmd(_DISPON)
        time.sleep_ms(100)

    # ── drawing primitives ────────────────────────────────────────

    def fill_rect(self, x, y, w, h, color):
        """Fill a rectangle with a solid colour."""
        if w <= 0 or h <= 0:
            return
        x1 = min(x + w - 1, self.w - 1)
        y1 = min(y + h - 1, self.h - 1)
        self._set_window(x, y, x1, y1)
        n  = (x1 - x + 1) * (y1 - y + 1)
        px = bytes([color >> 8, color & 0xFF])
        self.dc.on()
        self.cs.off()
        chunk = px * 256          # 512-byte block = 256 pixels
        full, rem = divmod(n, 256)
        for _ in range(full):
            self.spi.write(chunk)
        if rem:
            self.spi.write(px * rem)
        self.cs.on()

    def fill(self, color):
        self.fill_rect(0, 0, self.w, self.h, color)

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def rect(self, x, y, w, h, color):
        """Draw a hollow rectangle (outline only)."""
        self.hline(x,     y,       w, color)
        self.hline(x,     y + h - 1, w, color)
        self.vline(x,     y,       h, color)
        self.vline(x + w - 1, y,   h, color)

    def fill_circle(self, cx, cy, r, color):
        """Draw a filled circle using horizontal spans."""
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def draw_text(self, x, y, text, fg, bg=0, scale=1):
        """
        Render *text* at (x, y) using the built-in 8×8 framebuf font.

        Parameters
        ----------
        fg, bg : color565 values for foreground / background
        scale  : integer upscale factor (1 = 8 px tall, 2 = 16 px tall, …)

        Notes
        -----
        MicroPython's framebuf stores RGB-565 pixels little-endian;
        ILI9341 expects big-endian.  We reconstruct each pixel as a
        16-bit int (which equals the color565 value) and emit MSB-first.
        """
        if not text:
            return
        sw  = len(text) * 8          # source width in pixels (unscaled)
        buf = bytearray(sw * 8 * 2)  # RGB-565 buffer for 8 rows
        fb  = framebuf.FrameBuffer(buf, sw, 8, framebuf.RGB565)
        fb.fill(bg)
        fb.text(text, 0, 0, fg)

        tw = sw * scale              # target (scaled) width
        for row in range(8):
            # Build one horizontally-scaled row
            row_buf  = bytearray(tw * 2)
            src_base = row * sw * 2
            for col in range(sw):
                lo = buf[src_base + col * 2]
                hi = buf[src_base + col * 2 + 1]
                # Reconstruct the color565 value and emit big-endian
                c      = (hi << 8) | lo
                be_hi  = c >> 8
                be_lo  = c & 0xFF
                dst    = col * scale * 2
                for s in range(scale):
                    row_buf[dst + s * 2]     = be_hi
                    row_buf[dst + s * 2 + 1] = be_lo

            # Send the same row data `scale` times (vertical scale)
            self._set_window(x, y + row * scale,
                             x + tw - 1, y + row * scale + scale - 1)
            self.dc.on()
            self.cs.off()
            for _ in range(scale):
                self.spi.write(row_buf)
            self.cs.on()

    def draw_text_centered(self, cx, y, text, fg, bg=0, scale=1):
        """Draw text horizontally centred around pixel column *cx*."""
        pw = len(text) * 8 * scale
        self.draw_text(cx - pw // 2, y, text, fg, bg, scale)
