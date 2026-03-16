#!/usr/bin/env python3
"""
render-overlay.py
Renders the Now Playing overlay as a pixel-perfect transparent WebM video
using a headless browser — identical to what OBS shows.

Usage:
  Manual:  python render-overlay.py --artist "Burial" --title "Archangel" --duration 196
  Auto:    python render-overlay.py --auto
           (pulls current track from Beefweb — serve.bat must be running)

Output:
  A transparent .webm in the same folder, named after the track.
  Drop it into your video editor above your footage.

Requirements:
  pip install playwright
  playwright install chromium
  ffmpeg on PATH (already there if you have OBS)

The script looks for nowplaying-overlay.html in the same folder as itself.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "Missing dependency.\n\n"
        "Run these two commands first:\n"
        "  pip install playwright\n"
        "  playwright install chromium\n"
    )

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════
BEEFWEB_URL = 'http://localhost:8081/api/player?columns=%25artist%25,%25title%25,%25length_seconds%25'
SCRIPT_DIR  = Path(__file__).parent
OVERLAY_HTML= SCRIPT_DIR / 'nowplaying-overlay.html'

# Viewport size — must be big enough to fully contain the card + body padding
# The overlay uses body padding: 16px and card-width: 340px
VIEWPORT_W  = 340
VIEWPORT_H  = 100

FPS_INPUT   = 2
FPS_OUTPUT  = 30

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def fetch_from_beefweb():
    try:
        res  = urllib.request.urlopen(BEEFWEB_URL, timeout=5)
        data = json.loads(res.read())
        item = data['player']['activeItem']
        if item['index'] < 0:
            sys.exit("Nothing is playing in foobar2000.")
        artist   = item['columns'][0] or 'Unknown Artist'
        title    = item['columns'][1] or 'Unknown Track'
        duration = float(item['duration'])
        return artist, title, duration
    except Exception as e:
        sys.exit(
            f"Could not connect to Beefweb: {e}\n"
            "Make sure foobar2000 is running and serve.bat is active."
        )


def safe_filename(artist, title):
    raw  = f"{artist} - {title}"
    safe = re.sub(r'[^\w\s\-]', '', raw).strip()
    safe = re.sub(r'\s+', '_', safe)
    return safe or 'overlay'

# ═══════════════════════════════════════════════════════════════
#  RENDERER
# ═══════════════════════════════════════════════════════════════

def render(artist, title, duration, out_path, fps_in=FPS_INPUT, cover_band=True):
    if not OVERLAY_HTML.exists():
        sys.exit(
            f"Overlay HTML not found at:\n  {OVERLAY_HTML}\n"
            "Make sure nowplaying-overlay.html is in the same folder as this script."
        )

    total_frames = math.ceil(duration * fps_in)
    print(f"\n  Artist:   {artist}")
    print(f"  Title:    {title}")
    print(f"  Duration: {fmt_time(duration)} ({int(duration)}s)")
    print(f"  Frames:   {total_frames} @ {fps_in}fps → {FPS_OUTPUT}fps output")
    print(f"  Output:   {out_path}\n")

    # ── Temp folder for PNG frames ──────────────────────────────
    import shutil
    tmp_dir = SCRIPT_DIR / 'frames_tmp'
    tmp_dir.mkdir(exist_ok=True)
    print(f"  Temp:     {tmp_dir}\n")

    try:
        # ── Playwright headless browser ─────────────────────────
        print("Starting headless browser...")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page    = browser.new_page(
                viewport={'width': VIEWPORT_W, 'height': VIEWPORT_H}
            )

            page.goto(OVERLAY_HTML.as_uri())
            page.wait_for_load_state('networkidle')

            page.evaluate(f"""() => {{
                const artist = {json.dumps(artist)};
                const title  = {json.dumps(title)};
                const dur    = {duration};

                const card = document.getElementById('card');
                card.style.backdropFilter       = 'none';
                card.style.webkitBackdropFilter = 'none';
                card.style.border               = 'none';
                document.documentElement.style.setProperty('--card-blur', '0px');

                // Kill the polling loop so it doesn't interfere with our timer updates
                const highestId = setTimeout(() => {{}}, 0);
                for (let i = 0; i <= highestId; i++) {{
                    clearInterval(i);
                    clearTimeout(i);
                }}

                document.getElementById('artist').textContent = artist;
                document.getElementById('track').textContent  = title;
                card.classList.add('visible');
                window._dur = dur;

                // Remove ALL body spacing so card sits at exactly 340px
                document.body.style.padding = '0';
                document.body.style.margin  = '0';
                card.style.borderRadius = '20px';
                card.style.overflow     = 'hidden';

                // Single blurred dark band behind all content rows
                const cover = {str(cover_band).lower()};
                const content = card.querySelector('.content');
                if (cover && content) {{
                    const band = document.createElement('div');
                    band.style.cssText = `
                        position: absolute;
                        inset: -4px 0;
                        background: rgba(10,10,14,1.0);
                        filter: blur(4px);
                        z-index: 0;
                        pointer-events: none;
                    `;
                    content.style.position = 'relative';
                    content.insertBefore(band, content.firstChild);
                    content.querySelectorAll('.marquee-clip, .middle-row')
                        .forEach(el => {{
                            el.style.position = 'relative';
                            el.style.zIndex   = '1';
                        }});
                }}
            }}""")

            page.wait_for_timeout(600)

            print("Rendering frames...")
            for frame_num in range(total_frames):
                elapsed = frame_num / fps_in

                page.evaluate(f"""() => {{
                    const elapsed = {elapsed};
                    const dur     = window._dur;
                    const m  = Math.floor(elapsed / 60);
                    const s  = String(Math.floor(elapsed % 60)).padStart(2, '0');
                    const dm = Math.floor(dur / 60);
                    const ds = String(Math.floor(dur % 60)).padStart(2, '0');
                    document.getElementById('timer').textContent =
                        m + ':' + s + ' / ' + dm + ':' + ds;
                    const pct = dur > 0 ? Math.min(100, (elapsed / dur) * 100) : 0;
                    const fill = document.getElementById('progress-fill');
                    fill.style.transition = 'none';
                    fill.style.width = pct + '%';
                }}""")

                frame_path = tmp_dir / f"frame_{frame_num:06d}.png"
                page.screenshot(
                    path=str(frame_path),
                    type='png',
                    omit_background=True
                )

                pct = int((frame_num + 1) / total_frames * 40)
                bar = '█' * pct + '░' * (40 - pct)
                print(f"\r  [{bar}] {frame_num + 1}/{total_frames}  {fmt_time(elapsed)}", end='', flush=True)

            browser.close()

        print("\n\nEncoding video...")

        # ── ffmpeg encode from PNG sequence ──────────────────────
        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(fps_in),
            '-i', str(tmp_dir / 'frame_%06d.png'),
            '-vf', f'fps={FPS_OUTPUT}',
            '-c:v', 'prores_ks',
            '-profile:v', '4444',
            '-pix_fmt', 'yuva444p10le',
            str(out_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("\nffmpeg error:")
            print(result.stderr[-2000:])
            sys.exit("Encoding failed.")

        print(f"Done!  →  {out_path}")
        shutil.rmtree(tmp_dir, ignore_errors=True)

    except Exception as e:
        print(f"\nError: {e}")
        raise

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Render the Now Playing overlay as a transparent WebM video.'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--auto',     action='store_true',
                       help='Pull current track from Beefweb')
    group.add_argument('--artist',   type=str, help='Artist name')
    parser.add_argument('--title',    type=str)
    parser.add_argument('--duration', type=float, help='Duration in seconds')
    parser.add_argument('--out',      type=str, default=None,
                       help='Output filename (default: auto from track info)')
    parser.add_argument('--no-cover', action='store_true',
                       help='Skip the blurred cover band — pure transparent overlay, no bleed protection')

    args = parser.parse_args()

    if args.auto:
        print("Fetching track info from Beefweb...")
        artist, title, duration = fetch_from_beefweb()
    else:
        if not args.title or not args.duration:
            parser.error("--artist requires --title and --duration")
        artist, title, duration = args.artist, args.title, args.duration

    duration = math.ceil(duration)

    out_path = Path(args.out) if args.out else \
               SCRIPT_DIR / f"{safe_filename(artist, title)}.mov"

    render(artist, title, duration, out_path, cover_band=not args.no_cover)


if __name__ == '__main__':
    main()
