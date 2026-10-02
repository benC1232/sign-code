# sign-code

CircuitPython client for a 128×32 LED sign (the East Side Urbanism
TransitTracker hardware: an Adafruit MatrixPortal S3 driving two 64×32 HUB75
panels). It does no drawing of its own: every 30 s it fetches one full frame of
pixels from [sign-server](https://github.com/led-info-sign/sign-server) and
puts it on the panels.

Part of [led-info-sign](https://github.com/led-info-sign):

| Repo | Runs on | Does |
|------|---------|------|
| **sign-code** | the sign | Shows whatever pixels the server hands it |
| [sign-server](https://github.com/led-info-sign/sign-server) | a Raspberry Pi | Holds the screen; providers post panels to it |
| [weather-provider](https://github.com/led-info-sign/weather-provider) | a Raspberry Pi | Weather and rain radar panels |

## Frame format

`GET SIGN_SERVER_URL` must return exactly **8192 bytes**: 128×32 pixels in
RGB565, 2 bytes per pixel, little-endian (`RRRRRGGG GGGBBBBB` as a uint16), row
by row from the top-left. The bytes are copied straight into the display with
`bitmaptools.readinto`, so the sign does no per-pixel work.

## Behavior

- Fetches every `SIGN_REFRESH_S` seconds (30 by default).
- If a fetch fails, returns a non-200 status, or the body isn't 8192 bytes, the
  last frame stays on screen and it tries again on the next cycle. Errors are
  printed to the serial console.
- Reconnects to WiFi on its own if the connection drops.

## Install on the sign

Built against CircuitPython 10.0.x on the MatrixPortal S3. Copy to the
`CIRCUITPY` drive:

- `code.py`
- `settings.example.toml`, renamed to `settings.toml`, with your WiFi details
  and server URL filled in (it's gitignored so credentials stay out of the
  repo)

Libraries needed in `CIRCUITPY/lib`, from the
[Adafruit CircuitPython bundle](https://circuitpython.org/libraries):
`adafruit_matrixportal`, `adafruit_requests` and `adafruit_connection_manager`,
plus their dependencies. `bitmaptools` and `displayio` are built into the
firmware.

## Config (`settings.toml`)

| Key                       | Default | Meaning                                       |
|---------------------------|---------|-----------------------------------------------|
| `CIRCUITPY_WIFI_SSID`     | —       | WiFi network                                  |
| `CIRCUITPY_WIFI_PASSWORD` | —       | WiFi password                                 |
| `SIGN_SERVER_URL`         | —       | e.g. `http://<pi-address>:5001/frame`         |
| `SIGN_REFRESH_S`          | `30`    | Seconds between fetches                       |
| `SIGN_ROTATION`           | `180`   | Display rotation (0, 90, 180, 270)            |
| `SIGN_COLOR_ORDER`        | `"RBG"` | Panel color wiring; this sign needs `"RBG"`   |
| `SIGN_BIT_DEPTH`          | `5`     | Color depth per channel, 1–6                  |
