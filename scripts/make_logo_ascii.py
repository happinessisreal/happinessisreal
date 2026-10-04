"""One-off: turn each project logo into coloured ASCII for projects.svg.

    python scripts/make_logo_ascii.py      # reads scripts/data/logo-marks/*.png → scripts/data/logos.json

The PNGs are the logos' *marks* (background tile removed) on transparency, so only the
drawing becomes characters. Glyph weight follows how much of each cell the mark covers
(crisp edges, solid fills); colour is the mark's own, quantised to a few k-means
clusters like the portrait. The daily workflow only reads the JSON.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

RAMP = " .`:-=+*cs#%@"
COLS, K = 26, 4
DATA = Path(__file__).with_name("data")


def mark_ascii(png: Path):
    rgba = np.array(Image.open(png).convert("RGBA")).astype(np.float32)
    rgb, alpha = rgba[:, :, :3], rgba[:, :, 3] / 255.0
    if alpha.min() > 0.99:  # opaque raster (e.g. on white): everything that isn't white is the mark
        alpha = np.clip((255 - rgb.min(axis=2)) / 160.0, 0, 1)
        alpha = cv2.dilate(alpha, np.ones((5, 5), np.uint8))  # thin line art needs body to survive downsampling
    ys, xs = np.where(alpha > 0.1)  # crop to the mark so the drawing fills the grid
    m = int(0.04 * max(alpha.shape))
    y0, y1 = max(ys.min() - m, 0), min(ys.max() + m + 1, alpha.shape[0])
    x0, x1 = max(xs.min() - m, 0), min(xs.max() + m + 1, alpha.shape[1])
    rgb, alpha = rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
    h, w = alpha.shape
    rows = max(1, round(COLS * (h / w) * 0.48))
    cover = cv2.resize(alpha, (COLS, rows), interpolation=cv2.INTER_AREA)
    weighted = cv2.resize(rgb * alpha[:, :, None], (COLS, rows), interpolation=cv2.INTER_AREA)
    cell_rgb = np.clip(weighted / np.maximum(cover[:, :, None], 1e-6), 0, 255).astype(np.uint8)

    on = cover > 0.12
    lab = cv2.cvtColor(cell_rgb[None].reshape(1, -1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    labels = np.zeros(lab.shape[0], np.int32)
    picked = lab[on.ravel()]
    k = min(K, max(1, len(np.unique(picked.round(), axis=0))))
    cv2.setRNGSeed(7)
    _, lab_labels, centers = cv2.kmeans(picked, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.2),
                                        6, cv2.KMEANS_PP_CENTERS)
    labels[on.ravel()] = lab_labels.ravel()
    palette = []
    for c in cv2.cvtColor(centers.astype(np.uint8)[None], cv2.COLOR_LAB2RGB)[0]:
        hh, ss, vv = cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_RGB2HSV)[0, 0]
        r, g, b = cv2.cvtColor(np.uint8([[[hh, ss, max(int(vv), 120)]]]), cv2.COLOR_HSV2RGB)[0, 0]  # visible on dark
        palette.append(f"#{r:02x}{g:02x}{b:02x}")

    lum = cv2.cvtColor(cell_rgb, cv2.COLOR_RGB2LAB)[:, :, 0] / 255.0
    v = np.where(on, np.clip(cover, 0, 1) * (0.55 + 0.45 * lum), 0)
    idx = np.clip((v * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    lines = ["".join(RAMP[i] for i in row) for row in idx]
    colors = labels.reshape(rows, COLS).tolist()
    return lines, colors, palette


def main():
    logos = {}
    for png in sorted((DATA / "logo-marks").glob("*.png")):
        lines, colors, palette = mark_ascii(png)
        logos[png.stem] = {"lines": lines, "colors": colors, "palette": palette}
        print(png.stem, f"{COLS}x{len(lines)}", " ".join(palette))
    (DATA / "logos.json").write_text(json.dumps(logos, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
