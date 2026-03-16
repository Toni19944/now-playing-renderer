# now-playing-renderer

A companion tool for [obs-foobar-overlay](https://github.com/Toni19944/obs-foobar-overlay). When editing stream VODs where the music track isn't included, the overlay shows the wrong song. This tool renders a pixel-perfect transparent video of the overlay for any given track.

Uses a headless Chromium browser to render the actual overlay HTML, so the output is identical to what OBS shows — same fonts, same layout, same animations.

Output is a transparent ProRes 4444 `.mov` file, ready for DaVinci Resolve or any editor that supports alpha channels.

---

## Requirements

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/download.html) installed and on your system PATH — grab the latest full build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) if you're on Windows
- The `nowplaying-overlay.html` file from [obs-foobar-overlay](https://github.com/Toni19944/obs-foobar-overlay) placed in the same folder as the script. A copy of the overlay html is in this repo as well in case you need it.

Install Python dependencies:

```
pip install playwright
playwright install chromium
```

---

## Setup

Put these files all in the same folder:

```
📁 your folder
   render-overlay.py
   run-cover.bat
   run-nocover.bat
   nowplaying-overlay.html   ← copy from obs-foobar-overlay
```

> **Note:** Keep `nowplaying-overlay.html` up to date — if you change settings in the overlay, copy the updated file here too so the rendered video matches.

---

## Usage

### Auto mode — pull current track from foobar2000

The overlay server (`serve.bat` from obs-foobar-overlay) must be running and something must be playing in foobar2000.

**Double-click one of the bat files:**

| File | What it does |
|------|-------------|
| `run-cover.bat` | Renders with a subtle dark band behind the text rows to prevent old overlay text bleeding through in your editor |
| `run-nocover.bat` | Renders plain transparent overlay with no cover band |

Or run from terminal:

```bash
python render-overlay.py --auto
python render-overlay.py --auto --no-cover
```

### Manual mode — specify track info yourself

No foobar or server needed.

```bash
python render-overlay.py --artist "Burial" --title "Archangel" --duration 196
python render-overlay.py --artist "Burial" --title "Archangel" --duration 196 --no-cover
```

### Custom output filename

```bash
python render-overlay.py --auto --out "my-track.mov"
```

---

## The cover band

When you place the rendered overlay on top of footage that already has the live overlay baked in (showing a different song), the card's semi-transparent background lets the old text bleed through.

The `--no-cover` flag skips it — use this when your footage doesn't have the overlay baked in.

---

## Output

A `.mov` file named after the track (e.g. `Burial_-_Archangel.mov`) appears in the same folder as the script. In DaVinci Resolve, place it on a track above your footage — no extra settings needed, Resolve handles ProRes 4444 alpha natively.

---

## Configuration

Open `render-overlay.py` and adjust the values at the top:

| Variable | Default | Description |
|----------|---------|-------------|
| `BEEFWEB_URL` | `http://localhost:8081/...` | Beefweb proxy URL. Change port if you've changed it in `overlay-server.ps1`. |
| `VIEWPORT_W` | `340` | Render width in pixels — should match `--card-width` in your overlay. |
| `VIEWPORT_H` | `100` | Render height in pixels — adjust if your card height is different. |
| `FPS_INPUT` | `2` | Screenshots per second during rendering. 2 is plenty since the timer updates once per second. |
| `FPS_OUTPUT` | `30` | Output framerate after ffmpeg interpolation. |

---

## How it works

1. Launches a headless Chromium browser via Playwright
2. Loads `nowplaying-overlay.html` locally
3. Injects the track info directly into the page, bypassing the Beefweb fetch
4. Kills the overlay's polling loop so it doesn't interfere with the render
5. Screenshots the page once per second, updating the timer and progress bar each frame
6. Encodes the PNG sequence into a ProRes 4444 `.mov` via ffmpeg
7. Cleans up the temporary frame files automatically
