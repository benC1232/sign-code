# sign-code

CircuitPython client for a 128×32 LED sign. I'm running it on **DIY
TransitTracker hardware** (East Side Urbanism's TransitTracker design): an
Adafruit MatrixPortal S3 driving two 64×32 HUB75 panels.

The sign does no drawing of its own. Every 30 s it fetches one full frame of
pixels from a server and puts it on the panels. Everything you see is drawn
elsewhere:

| Part | Runs on | Does |
|------|---------|------|
| **sign-code** (this repo) | the sign | Shows whatever pixels the server hands it |
| [sign-server](https://github.com/benC1232/sign-server) | a Raspberry Pi | Holds the screen; providers post panels to it |
| weather-provider | a Raspberry Pi | Weather and rain radar panels |

weather-provider isn't published yet. Any HTTP server that returns frames in
the format below works in place of sign-server.

## Frame format

`GET SIGN_SERVER_URL` returns **1 to 30 frames** back to back, each **8192
bytes**: 128×32 pixels in RGB565, 2 bytes per pixel, little-endian
(`RRRRRGGG GGGBBBBB` as a uint16), row by row from the top-left.

- **One frame** is a still image.
- **Several frames** are an animation. The `X-Frame-Ms` response header says
  how long to show each one, and the sign loops them until the next poll.

Each frame is copied straight into the display with `bitmaptools.readinto`, so
the sign does no per-pixel work. 30 frames is about 240 KB, well within the
MatrixPortal S3's memory (it prints its free memory at startup).

## Behavior

- Fetches every `SIGN_REFRESH_S` seconds (30 by default).
- If a fetch fails, returns a non-200 status, or the body isn't a whole number
  of 8192-byte frames (1–30), the last frames stay on screen and it tries again
  on the next cycle. After
  `SIGN_NO_SIGNAL_AFTER` failures in a row (2 by default, about a minute) it
  shows **NO SIGNAL** in rainbow colors instead, and goes back to the picture
  as soon as a frame arrives. Errors are printed to the serial console.
- Reconnects to WiFi on its own if the connection drops (showing NO SIGNAL
  while it can't).

## Install on the sign

Built against CircuitPython 10.0.x on the MatrixPortal S3. Copy to the
`CIRCUITPY` drive:

- `code.py`
- `settings.example.toml`, renamed to `settings.toml`, with your WiFi details
  and server URL filled in (it's gitignored so credentials stay out of the
  repo)

Libraries needed in `CIRCUITPY/lib`, from the
[Adafruit CircuitPython bundle](https://circuitpython.org/libraries):
`adafruit_matrixportal`, `adafruit_requests`, `adafruit_connection_manager` and
`adafruit_display_text`, plus their dependencies. `bitmaptools` and `displayio` are built into the
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
| `SIGN_NO_SIGNAL_AFTER`    | `2`     | Failed fetches in a row before NO SIGNAL      |

## License

MIT, see [LICENSE](LICENSE).
