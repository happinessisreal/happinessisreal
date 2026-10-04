"""One-off: build the JetBrains Mono subsets that generate_stats.py inlines.

    pip install fonttools brotli && python scripts/build_fonts.py

Prebuilding keeps the scheduled workflow dependency-free (stdlib only).
"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

FONTS = Path(__file__).with_name("fonts")
CHARS = "".join(chr(c) for c in range(32, 127)) + "·–—→←↑↓…×%°"

for weight, name in [(400, "Regular"), (600, "SemiBold")]:
    font = TTFont(FONTS / f"JetBrainsMono-{name}.ttf", recalcTimestamp=False)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.hinting = False
    sub = subset.Subsetter(opts)
    sub.populate(text=CHARS)
    sub.subset(font)
    font.flavor = "woff2"
    out = FONTS / f"jbm-latin-{weight}.woff2"
    font.save(out)
    print(out.name, out.stat().st_size, "bytes")
