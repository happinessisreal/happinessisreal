"""Turn a picture into ascii.svg: a self-typing ASCII portrait.

    pip install pillow numpy opencv-python-headless rembg onnxruntime fonttools brotli
    python scripts/make_portrait.py images.jpg

Pipeline (each stage earns its place):
  cut-out            background → white, i.e. the blank end of the ramp
                     (--mask rembg for photos, --mask sky for a subject against sky)
  bilateral filter   smooth flat areas, keep edges
  CLAHE              local contrast, so a flatly lit subject isn't one tone
  levels + curve     clip at --white, then (v)^gamma keeps thin features (eyes, outlines) alive
  ramp mapping       ' .`:-=+*cs#%@' light → dark; the leading space clears the background
  red layer          cells that are genuinely red (lips, cheeks) are drawn in a second colour

Each row is revealed by a clipPath whose width animates 0 → full with a cursor block
riding the edge; rows start 0.09 s apart and freeze when done (prints once, no loop).
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from svgkit import font_face, svg_doc

RAMP = " .`:-=+*cs#%@"
FONT_SIZE = 12.9
CHAR_W = FONT_SIZE * 0.6  # JetBrains Mono advance = 600/1000 em
LINE_H = 15.0
PAD = 14.0
STEP = 0.09  # seconds per row


def sky_mask(rgb: np.ndarray) -> np.ndarray:
    """Alpha for a subject in front of sky: blue or cloud-white regions *touching the
    border* become background, so white details inside the subject (eye highlights) stay."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    candidate = (((h >= 90) & (h <= 135) & (s > 50) & (v > 70)) | ((s < 45) & (v > 185))).astype(np.uint8)
    n, labels = cv2.connectedComponents(candidate, connectivity=4)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    bg = np.isin(labels, [b for b in border if b != 0])
    bg = cv2.morphologyEx(bg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    return np.where(bg, 0, 255).astype(np.uint8)


def cut_out(img: Image.Image, mask: str) -> np.ndarray:
    """RGBA array with the background made transparent."""
    rgb = np.array(img.convert("RGB"))
    if mask == "rembg":  # best for real photos; downloads a large model on first run
        from rembg import remove
        return np.array(remove(img.convert("RGB")))
    alpha = sky_mask(rgb) if mask == "sky" else np.full(rgb.shape[:2], 255, np.uint8)
    return np.dstack([rgb, alpha])


def to_ascii(img: Image.Image, cols: int, gamma: float, clahe_clip: float, mask: str, white_point: float = 1.0, edge_boost: float = 0.0, red_share: float = 0.35):
    rgba = cut_out(img, mask)
    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > 32)
    if len(xs):  # crop to the subject
        rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        alpha = rgba[:, :, 3]
    white = np.full(rgba.shape[:2] + (3,), 255, np.uint8)
    a = (alpha[:, :, None] / 255.0)
    rgb = (rgba[:, :, :3] * a + white * (1 - a)).astype(np.uint8)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 60, 60)
    gray = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8)).apply(gray)
    v = np.clip((gray / 255.0) / white_point, 0, 1) ** gamma  # levels: >= white point → blank
    if edge_boost > 0:  # bolder outlines: darken detected edges (good for cartoons / line art)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 60, 140)
        edges = cv2.dilate(edges, np.ones((2, 2), np.uint8)) > 0
        v[edges] *= 1 - edge_boost
    v[alpha < 32] = 1.0  # background stays blank

    h, w = v.shape
    rows = max(1, round(cols * (h / w) * 0.48))  # monospace cells are ~2x taller than wide
    small = cv2.resize(v.astype(np.float32), (cols, rows), interpolation=cv2.INTER_AREA)
    idx = np.clip(((1 - small) * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)

    # Regions that are genuinely red (lips, tongue, cheeks) get their own colour layer.
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    red = (((hsv[:, :, 0] <= 10) | (hsv[:, :, 0] >= 168)) & (hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 70) & (alpha >= 32))
    red_cells = cv2.resize(red.astype(np.float32), (cols, rows), interpolation=cv2.INTER_AREA) > red_share

    grid = [("".join(RAMP[i] for i in row), "".join("1" if r else "0" for r in rrow)) for row, rrow in zip(idx, red_cells)]
    while grid and not grid[0][0].strip():
        grid.pop(0)
    while grid and not grid[-1][0].strip():
        grid.pop()
    return [g[0].rstrip() for g in grid], [g[1] for g in grid]


def to_svg(lines: list[str], red_rows: list[str], cols: int) -> str:
    width = PAD * 2 + cols * CHAR_W
    height = PAD * 2 + len(lines) * LINE_H
    parts = []
    t = 0.0
    for i, (line, red) in enumerate(zip(lines, red_rows)):
        y = PAD + i * LINE_H
        full = len(line) * CHAR_W
        if not line.strip():
            continue
        main_layer = "".join(" " if red[j] == "1" else ch for j, ch in enumerate(line)).rstrip()
        red_layer = "".join(ch if red[j] == "1" else " " for j, ch in enumerate(line)).rstrip()
        x0 = PAD + (len(line) - len(line.lstrip())) * CHAR_W  # start the wipe at the first glyph
        dur = max(0.04, STEP * (len(line.strip()) / cols) * 1.6)
        texts = f'<text xml:space="preserve" x="{PAD}" y="{y + 11.2:.1f}" class="acc" font-size="{FONT_SIZE}">{main_layer}</text>'
        if red_layer.strip():
            texts += f'<text xml:space="preserve" x="{PAD}" y="{y + 11.2:.1f}" class="red" font-size="{FONT_SIZE}">{red_layer}</text>'
        parts.append(
            f'<clipPath id="r{i}"><rect x="{x0:.1f}" y="{y:.1f}" height="{LINE_H:.0f}" width="0">'
            f'<animate attributeName="width" from="0" to="{PAD + full - x0:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
            f'</rect></clipPath>'
            f'<g clip-path="url(#r{i})">{texts}</g>'
            f'<rect y="{y + 1.5:.1f}" width="6" height="12" class="acc" opacity="0">'
            f'<animate attributeName="x" from="{x0:.1f}" to="{PAD + full:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{t:.2f}s"/><set attributeName="opacity" to="0" begin="{t + dur:.2f}s"/></rect>'
        )
        t += STEP
    return svg_doc(width, height, "".join(parts), font_face(RAMP))


def to_color_ascii(img: Image.Image, cols: int, k: int, gamma: float, cutout: bool = False, sat_boost: float = 0.0):
    """Full-colour mode: the whole picture (background included) for a dark panel.

    Density comes from brightness (bright → dense, black → empty), and colour from the
    image quantised to `k` k-means clusters, so each region gets one deliberate colour
    instead of per-character noise.
    """
    rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    rows = max(1, round(cols * (h / w) * 0.48))
    cells = cv2.resize(rgb, (cols, rows), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(cells, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(7)  # deterministic clusters → byte-identical output for the same input
    _, labels, centers = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.2),
                                    6, cv2.KMEANS_PP_CENTERS)
    palette = cv2.cvtColor(centers.astype(np.uint8)[None], cv2.COLOR_LAB2RGB)[0]
    hexes = []
    for r, g, b in palette:  # lift very dark colours so their sparse glyphs stay visible on the panel
        hh, ss, vv = cv2.cvtColor(np.uint8([[[r, g, b]]]), cv2.COLOR_RGB2HSV)[0, 0]
        vv = max(int(vv), 115)
        r2, g2, b2 = cv2.cvtColor(np.uint8([[[hh, ss, vv]]]), cv2.COLOR_HSV2RGB)[0, 0]
        hexes.append(f"#{r2:02x}{g2:02x}{b2:02x}")
    lum = lab[:, 0].reshape(rows, cols) / 255.0
    sat = cv2.cvtColor(cells, cv2.COLOR_RGB2HSV)[:, :, 1] / 255.0
    # bright → dense on the dark panel; strongly coloured areas (cheeks, tongue) get a
    # little extra weight so they read as solid colour rather than mid-grey texture
    v = np.clip(lum ** gamma + sat_boost * sat, 0, 1)
    # Outlines become sparse glyphs, so shapes read as drawn lines.
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.dilate(cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 60, 140), np.ones((3, 3), np.uint8))
    edge_cells = cv2.resize((edges > 0).astype(np.float32), (cols, rows), interpolation=cv2.INTER_AREA)
    v = v * (1 - 0.75 * np.clip(edge_cells * 2.2, 0, 1))
    idx = np.clip((v * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    labels = labels.reshape(rows, cols)
    if cutout:  # ASCII the whole picture first, then cut the subject out of it
        keep = cv2.resize(sky_mask(rgb).astype(np.float32) / 255.0, (cols, rows), interpolation=cv2.INTER_AREA) >= 0.5
        idx = np.where(keep, idx, 0)  # RAMP[0] is a space
    lines = ["".join(RAMP[i] for i in row) for row in idx]
    colors = [[int(c) for c in row] for row in labels]
    return lines, colors, hexes


def to_color_svg(lines, colors, hexes, cols: int, panel: str = "#0d1117") -> str:
    inset = PAD + 8
    width = inset * 2 + cols * CHAR_W
    height = inset * 2 + len(lines) * LINE_H
    css = "".join(f".k{i}{{fill:{h}}}" for i, h in enumerate(hexes))
    parts = [f'<rect width="{width:.1f}" height="{height:.1f}" rx="18" fill="{panel}"/>']
    t = 0.0
    for i, (line, crow) in enumerate(zip(lines, colors)):
        y = inset + i * LINE_H
        if not line.strip():
            t += STEP
            continue
        texts = ""
        for c in sorted(set(crow)):
            layer = "".join(ch if crow[j] == c else " " for j, ch in enumerate(line)).rstrip()
            if layer.strip():
                texts += f'<text xml:space="preserve" x="{inset}" y="{y + 11.2:.1f}" class="k{c}" font-size="{FONT_SIZE}">{layer}</text>'
        full = len(line.rstrip()) * CHAR_W
        dur = STEP * 1.6
        parts.append(
            f'<clipPath id="r{i}"><rect x="{inset}" y="{y:.1f}" height="{LINE_H:.0f}" width="0">'
            f'<animate attributeName="width" from="0" to="{full:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
            f'</rect></clipPath><g clip-path="url(#r{i})">{texts}</g>'
            f'<rect y="{y + 1.5:.1f}" width="6" height="12" fill="#f0f6fc" opacity="0">'
            f'<animate attributeName="x" from="{inset}" to="{inset + full:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.8" begin="{t:.2f}s"/><set attributeName="opacity" to="0" begin="{t + dur:.2f}s"/></rect>'
        )
        t += STEP
    return svg_doc(width, height, "".join(parts), font_face(RAMP), css)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default="ascii.svg")
    ap.add_argument("--cols", type=int, default=90)
    ap.add_argument("--gamma", type=float, default=1.7)
    ap.add_argument("--clahe", type=float, default=3.0)
    ap.add_argument("--white", type=float, default=1.0,
                    help="white point (0-1); lower it to blank flat light fills, e.g. cartoons")
    ap.add_argument("--mask", choices=["rembg", "sky", "none"], default="rembg",
                    help="background removal: rembg (photos), sky (cartoon on sky), none")
    ap.add_argument("--edges", type=float, default=0.0, help="0-1: darken detected outlines (cartoons)")
    ap.add_argument("--trim", type=int, default=0, help="crop this many pixels off every edge (scan/JPEG frames)")
    ap.add_argument("--color", type=int, default=0, metavar="K",
                    help="full-colour mode with K quantised colours on a dark panel (keeps the background)")
    ap.add_argument("--sat-boost", type=float, default=0.0, help="with --color: extra density for saturated colours (0-0.4)")
    ap.add_argument("--cutout", action="store_true", help="with --color: blank the background cells (uses the sky mask)")
    ap.add_argument("--print", action="store_true", help="also print the ASCII to stdout")
    a = ap.parse_args()
    img = Image.open(a.image)
    if a.trim:
        img = img.crop((a.trim, a.trim, img.width - a.trim, img.height - a.trim))
    if a.color:
        lines, colors, hexes = to_color_ascii(img, a.cols, a.color, a.gamma, a.cutout, a.sat_boost)
        Path(a.out).write_text(to_color_svg(lines, colors, hexes, a.cols), encoding="utf-8")
        print("palette:", " ".join(hexes))
    else:
        lines, red_rows = to_ascii(img, a.cols, a.gamma, a.clahe, a.mask, a.white, a.edges)
        Path(a.out).write_text(to_svg(lines, red_rows, a.cols), encoding="utf-8")
    if a.print:
        print("\n".join(lines))
    print(f"wrote {a.out}: {a.cols} cols x {len(lines)} rows")


if __name__ == "__main__":
    main()
