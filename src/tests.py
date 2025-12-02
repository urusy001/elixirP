import os
import re
from pathlib import Path
from PIL import Image

# Your folder with frames
FOLDER = Path("/Users/paylakurusyan/Downloads/ezgif-split/png_output")
OUTPUT_GIF = FOLDER / "utya-shop.gif"

# Filenames like:
# frame_00_delay-0.03s_frame_000.png
#       ^^          ^^^^^
#       idx         delay (s)
pattern = re.compile(
    r"^frame_(\d+)_delay-([\d.]+)s_.*\.(png|jpg|jpeg)$",
    re.IGNORECASE,
)

def collect_frames(folder: Path):
    entries = []

    for fname in os.listdir(folder):
        m = pattern.match(fname)
        if not m:
            continue

        frame_idx = int(m.group(1))          # 00
        delay_s = float(m.group(2))          # 0.03
        path = folder / fname

        entries.append({
            "path": path,
            "frame_idx": frame_idx,
            "delay_ms": int(delay_s * 1000),  # Pillow uses ms
        })

    # sort ONLY by frame index (ignore any sub-index)
    entries.sort(key=lambda e: e["frame_idx"])
    return entries

def make_gif():
    frames_meta = collect_frames(FOLDER)
    if not frames_meta:
        raise RuntimeError("No matching frames found in folder")

    pil_frames = []
    durations = []

    for meta in frames_meta:
        img = Image.open(meta["path"]).convert("RGBA")
        pil_frames.append(img)
        durations.append(meta["delay_ms"])

    # normalize all frames to first frame size (just in case)
    w, h = pil_frames[0].size
    pil_frames = [
        f.resize((w, h), Image.Resampling.LANCZOS) for f in pil_frames
    ]

    # save GIF with per-frame durations
    pil_frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=pil_frames[1:],
        duration=durations,   # list of per-frame delays (ms)
        loop=0,               # 0 = infinite loop
        disposal=2,
    )

    print(f"Saved GIF → {OUTPUT_GIF}")

if __name__ == "__main__":
    make_gif()