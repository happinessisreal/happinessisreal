"""Shared bits for every generated SVG: palette, inlined font subsets, escaping.

GitHub strips CSS and scripts from READMEs, but an SVG loaded through <img> keeps
its own <style> — so each file carries its palette (light + dark via
prefers-color-scheme) and a base64 @font-face subset to exactly the characters it
draws. External font URLs can't work: browsers block subresources of image documents.
"""
import base64
import io
from pathlib import Path
from xml.sax.saxutils import escape

FONTS = Path(__file__).with_name("fonts")
FAMILY = "JBM,ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

# GitHub's own greys + one amber accent (the portrait's colour).
LIGHT = {"ink": "#1f2328", "mut": "#59636e", "fnt": "#8c959f", "rule": "#d1d9e0", "acc": "#9a6700", "accs": "#d4a72c", "red": "#cf222e"}
DARK = {"ink": "#f0f6fc", "mut": "#9198a1", "fnt": "#6e7681", "rule": "#30363d", "acc": "#e3b341", "accs": "#bb8009", "red": "#ff7b72"}


def palette_css() -> str:
    def rules(p):
        return (f".red{{fill:{p['red']}}}.ink{{fill:{p['ink']}}}.mut{{fill:{p['mut']}}}.fnt{{fill:{p['fnt']}}}.acc{{fill:{p['acc']}}}"
                f".accs{{stroke:{p['accs']}}}.rule{{stroke:{p['rule']}}}.trk{{fill:{p['rule']}}}.soft{{fill:{p['accs']};opacity:.22}}")
    return rules(LIGHT) + "@media(prefers-color-scheme:dark){" + rules(DARK) + "}"


def prebuilt_face(weight: int = 400) -> str:
    """@font-face from the committed latin subset (no fontTools needed; used in CI)."""
    data = (FONTS / f"jbm-latin-{weight}.woff2").read_bytes()
    return (f"@font-face{{font-family:JBM;font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{base64.b64encode(data).decode()}) format('woff2')}}")


def font_face(text: str, weight: int = 400) -> str:
    """@font-face rule embedding JetBrains Mono subset to the characters in `text`."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    src = FONTS / ("JetBrainsMono-SemiBold.ttf" if weight >= 600 else "JetBrainsMono-Regular.ttf")
    font = TTFont(src, recalcTimestamp=False)  # no save-time timestamp → reproducible output
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.hinting = False
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(set(text + " "))))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:JBM;font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


def svg_doc(width: float, height: float, body: str, fonts: str, extra_css: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
            f'viewBox="0 0 {width:g} {height:g}" fill="none" font-family="{escape(FAMILY)}">'
            f"<style>{fonts}{palette_css()}{extra_css}</style>{body}</svg>\n")


def text_of(svg_body: str) -> str:
    """Characters that appear in <text> nodes (for subsetting)."""
    import re
    return "".join(re.findall(r">([^<>]*)</text>", svg_body))


def esc(s: str) -> str:
    return escape(s)
