# Shows whatever sign-server sends: full frames of raw RGB565 pixels
# (little-endian uint16, row-major from the top-left), polled on a fixed
# interval. One frame is a still image; up to 30 back to back are an
# animation, looped at the X-Frame-Ms header's speed until the next poll.
# When frames stop coming it shows "NO SIGNAL" in rainbow colors until
# they're back. Config lives in settings.toml.

import gc
import io
import os
import time

import adafruit_connection_manager
import adafruit_requests
import bitmaptools
import displayio
import terminalio
import wifi
from adafruit_display_text import label
from adafruit_matrixportal.matrix import Matrix

WIDTH = 128
HEIGHT = 32
FRAME_BYTES = WIDTH * HEIGHT * 2
MAX_FRAMES = 30  # animations: up to 30 frames in one response

SERVER_URL = os.getenv("SIGN_SERVER_URL")
REFRESH_S = os.getenv("SIGN_REFRESH_S", 30)
ROTATION = os.getenv("SIGN_ROTATION", 180)
COLOR_ORDER = os.getenv("SIGN_COLOR_ORDER", "RBG")
BIT_DEPTH = os.getenv("SIGN_BIT_DEPTH", 5)
NO_SIGNAL_AFTER = os.getenv("SIGN_NO_SIGNAL_AFTER", 2)  # failed fetches in a row

matrix = Matrix(width=WIDTH, height=HEIGHT, bit_depth=BIT_DEPTH, color_order=COLOR_ORDER)
display = matrix.display
display.rotation = ROTATION
display.auto_refresh = False

bitmap = displayio.Bitmap(WIDTH, HEIGHT, 65536)
converter = displayio.ColorConverter(input_colorspace=displayio.Colorspace.RGB565)
frame_group = displayio.Group()
frame_group.append(displayio.TileGrid(bitmap, pixel_shader=converter))
display.root_group = frame_group
display.refresh()


def rainbow(n):
    """n colors from red through violet, as 0xRRGGBB."""
    colors = []
    for i in range(n):
        h = i * 5 / n  # 0..5 around the hue wheel, stopping short of red again
        f = h - int(h)
        r, g, b = [(1, f, 0), (1 - f, 1, 0), (0, 1, f), (0, 1 - f, 1), (f, 0, 1)][int(h)]
        colors.append((int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255))
    return colors


def no_signal_screen(text="NO SIGNAL", scale=2):
    """Each letter its own label so it can have its own rainbow color."""
    group = displayio.Group()
    char_w = terminalio.FONT.get_bounding_box()[0] * scale
    x = (WIDTH - char_w * len(text)) // 2
    for ch, color in zip(text, rainbow(len(text))):
        if ch != " ":
            letter = label.Label(terminalio.FONT, text=ch, color=color, scale=scale)
            letter.anchor_point = (0, 0.5)
            letter.anchored_position = (x, HEIGHT // 2)
            group.append(letter)
        x += char_w
    return group


no_signal_group = no_signal_screen()


def show_no_signal():
    if display.root_group is not no_signal_group:
        print("No signal")
        display.root_group = no_signal_group
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
            show_no_signal()
            time.sleep(5)
    print("IP:", wifi.radio.ipv4_address)


connect()
pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
requests = adafruit_requests.Session(pool, ssl_context)

def header(resp, name):
    """Case-insensitive response header lookup."""
    name = name.lower()
    for key, value in resp.headers.items():
        if key.lower() == name:
            return value
    return None


def fetch():
    """Returns (pixels, frame count, ms per frame). One frame means a still image."""
    connect()
    with requests.get(SERVER_URL, timeout=10) as resp:
        if resp.status_code != 200:
            raise RuntimeError("HTTP %d" % resp.status_code)
        frame_ms = int(header(resp, "X-Frame-Ms") or 0)
        pixels = resp.content
    count, extra = divmod(len(pixels), FRAME_BYTES)
    if extra or not 1 <= count <= MAX_FRAMES:
        raise ValueError("expected 1-%d frames of %d bytes, got %d bytes" % (MAX_FRAMES, FRAME_BYTES, len(pixels)))
    return pixels, count, frame_ms


def show_frame(pixels, index):
    start = index * FRAME_BYTES
    bitmaptools.readinto(bitmap, io.BytesIO(pixels[start : start + FRAME_BYTES]), 16, element_size=2)
    display.root_group = frame_group
    display.refresh()


gc.collect()
print("Free memory:", gc.mem_free(), "bytes; up to", MAX_FRAMES * FRAME_BYTES, "needed for", MAX_FRAMES, "frames")
print("Fetching frames from", SERVER_URL, "every", REFRESH_S, "s")
failures = 0
pixels, count, frame_ms = None, 1, 0
index = 0
next_poll = time.monotonic()
while True:
    if time.monotonic() >= next_poll:
        next_poll = time.monotonic() + REFRESH_S
        try:
            pixels, count, frame_ms = fetch()
            failures = 0
            index = 0
            gc.collect()
        except Exception as e:  # keep the last frames up for a blip, then say so
            failures += 1
            print("Frame error:", e)
            if failures >= NO_SIGNAL_AFTER:
                pixels = None
                show_no_signal()

    if pixels is None:
        time.sleep(max(0, next_poll - time.monotonic()))
    elif count == 1 or frame_ms <= 0:
        show_frame(pixels, 0)  # still image: show it and wait for the next poll
        time.sleep(max(0, next_poll - time.monotonic()))
    else:
        show_frame(pixels, index)  # animation: step through the frames until the next poll
        index = (index + 1) % count
        time.sleep(max(0, min(frame_ms / 1000, next_poll - time.monotonic())))
