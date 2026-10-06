"""Download the Noto fonts (SIL Open Font License) used by the templates into assets/fonts/.

Optional: without them Chromium falls back to OS fonts, which works but makes output vary across
machines. Run once:  uv run python scripts/fetch_fonts.py
"""

from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://github.com/google/fonts/raw/main/ofl/"
FONTS = [
    "notosans/NotoSans[wdth,wght].ttf",
    "notoserif/NotoSerif[wdth,wght].ttf",
    "notosansmono/NotoSansMono[wdth,wght].ttf",
    "notonaskharabic/NotoNaskhArabic[wght].ttf",
    "notosanssc/NotoSansSC[wght].ttf",
    "notosansjp/NotoSansJP[wght].ttf",
    "notosansdevanagari/NotoSansDevanagari[wdth,wght].ttf",
]
DEST = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for rel in FONTS:
        target = DEST / Path(rel).name
        if target.exists():
            print(f"✓ {target.name} (already present)")
            continue
        url = BASE + urllib.parse.quote(rel)
        print(f"↓ {target.name} …", end=" ", flush=True)
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                target.write_bytes(resp.read())
            print(f"{target.stat().st_size / 1e6:.1f} MB")
        except Exception as e:  # keep going; missing fonts just fall back to OS fonts
            print(f"failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
