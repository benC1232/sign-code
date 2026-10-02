# Shows whatever sign-server sends: one full frame of raw RGB565 pixels
# (little-endian uint16, row-major from the top-left), polled on a fixed
# interval. Config lives in settings.toml.

import io
import os
import time

import adafruit_connection_manager
import adafruit_requests
import bitmaptools
import displayio
import wifi
from adafruit_matrixportal.matrix import Matrix

WIDTH = 128
HEIGHT = 32
FRAME_BYTES = WIDTH * HEIGHT * 2

SERVER_URL = os.getenv("SIGN_SERVER_URL")
REFRESH_S = os.getenv("SIGN_REFRESH_S", 30)
ROTATION = os.getenv("SIGN_ROTATION", 180)
COLOR_ORDER = os.getenv("SIGN_COLOR_ORDER", "RBG")
BIT_DEPTH = os.getenv("SIGN_BIT_DEPTH", 5)

matrix = Matrix(width=WIDTH, height=HEIGHT, bit_depth=BIT_DEPTH, color_order=COLOR_ORDER)
display = matrix.display
display.rotation = ROTATION
display.auto_refresh = False

bitmap = displayio.Bitmap(WIDTH, HEIGHT, 65536)
converter = displayio.ColorConverter(input_colorspace=displayio.Colorspace.RGB565)
root = displayio.Group()
root.append(displayio.TileGrid(bitmap, pixel_shader=converter))
display.root_group = root
display.refresh()


def connect():
    """Connect (or reconnect) to WiFi; returns at once if already connected."""
    if wifi.radio.connected:
        return
    while not wifi.radio.connected:
        print("Connecting to", os.getenv("CIRCUITPY_WIFI_SSID"))
        try:
            wifi.radio.connect(
                os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")
            )
        except ConnectionError as e:
            print("WiFi failed:", e)
            time.sleep(5)
    print("IP:", wifi.radio.ipv4_address)


connect()
pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
requests = adafruit_requests.Session(pool, ssl_context)

print("Fetching frames from", SERVER_URL, "every", REFRESH_S, "s")
while True:
    started = time.monotonic()
    try:
        connect()
        with requests.get(SERVER_URL, timeout=10) as resp:
            if resp.status_code != 200:
                raise RuntimeError("HTTP %d" % resp.status_code)
            pixels = resp.content
        if len(pixels) != FRAME_BYTES:
            raise ValueError("expected %d bytes, got %d" % (FRAME_BYTES, len(pixels)))
        bitmaptools.readinto(bitmap, io.BytesIO(pixels), 16, element_size=2)
        display.refresh()
    except Exception as e:  # keep the last frame up and try again next time
        print("Frame error:", e)
    time.sleep(max(0, REFRESH_S - (time.monotonic() - started)))
